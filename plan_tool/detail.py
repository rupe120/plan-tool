"""Author developer-actionable per-step implementation detail markdown files.

Audience for the output is **a developer who will implement the step** —
the prompt template enforces a seven-section structure (Summary / Table
of Contents / Why / Files / Implementation / Tests / Acceptance
criteria, plus optional References / Deferred) and asks claude to cite
specific file paths, function names, and line ranges. Summary and Table
of Contents are reviewer-facing scaffolding so a person auditing the
file can orient before diving in.

This module ships in three layers built up across plan steps:

- **Step 1 (here)** — pure helpers: slug derivation, output-path
  resolution, prompt rendering, response extraction. No I/O, no claude.
- **Step 2** — frontmatter mutation: round-trip a plan to set
  ``step.detail`` after the file is written.
- **Step 3** — orchestrator + ``plan-tool detail`` CLI subcommand.

Step 1's surface is intentionally narrow so it's testable in isolation
without filesystem fixtures or a fake claude invoker.
"""

from __future__ import annotations

import contextlib
import copy
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Callable, NamedTuple, Optional, Sequence, TextIO

if TYPE_CHECKING:
    from plan_tool.review import Recommendation

from plan_tool.checkpoint import (
    Checkpoint,
    checkpoint_path,
    compute_input_hash,
    discard_checkpoint,
    load_if_valid,
    save_checkpoint,
)
from plan_tool.convergence import (
    ConvergenceState,
    DEFAULT_MAX_ITERATIONS,
    IterativeBudget,
    larger_iteration_budget_seconds,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.concept_tree import (
    ConceptNode,
    ConceptTree,
    InvalidConceptTreeError,
    RECORD_KIND_DECISION,
    RECORD_KIND_FULL_TREE,
    StaleConceptTreeError,
    load_concepts,
    save_concepts,
)
from plan_tool.concept_bootstrap import (
    bootstrap_concepts,
    empty_concept_headings_message,
)
# Canonical path derivation and slug rules live in the
# ``plan_tool.detail_artifacts`` leaf (shared with ``fingerprint``/
# ``review``/``scope_out``); re-imported here so every historical
# ``plan_tool.detail`` import path keeps returning the same objects.
from plan_tool.detail_artifacts import (
    DetailFormatError,
    _DETAIL_FORMAT_VERSION_MARKER_RE,
    _MAX_SLUG_LEN,
    _SLUG_FALLBACK,
    _SLUG_STOPWORDS,
    _line_terminator,
    _plan_slug,
    derive_detail_path,
    derive_step_slug,
    find_unreferenced_detail_for_step,
    locate_detail_format_carrier,
    render_detail_format_version_marker,
    require_supported_detail_format_version,
    strip_detail_format_version_marker,
)
# The plan scope-fence renderer and its section-recognition rules live in the
# ``plan_tool.scope_fence`` leaf (shared with ``create``, and with ``renderer``
# once the run lane renders the fence); re-imported here so every historical
# ``plan_tool.detail`` import path keeps returning the same objects. NOTE: the
# leaf's plan-body ``_H2_HEADING_RE`` is deliberately NOT imported — this
# module's same-named regex grabs a *detail file's* first heading word and
# would be shadowed by it.
from plan_tool.scope_fence import (
    _fence_run_closes,
    _fenced_code_spans,
    _DETAIL_FENCE_SECTIONS,
    _FENCE_CLOSE_RE,
    _FENCE_OPEN_RE,
    _SECTION_PLACEHOLDER_RE,
    _is_placeholder_section,
    _strip_frontmatter,
    collapse_intent_to_one_line,
    extract_h2_sections,
    extract_plan_guardrails,
    is_placeholder_intent,
    render_scope_fence,
)
# Module-level import (vs. lazy) so tests can monkeypatch
# ``plan_tool.detail.apply_finding``. Safe at load time because
# ``plan_tool.review``'s imports from ``plan_tool.detail`` (used by
# launcher-side primitives) are themselves lazy (call-time), so the
# load graph stays a tree.
from plan_tool.backend import spawn_cwd_from_repo_root
from plan_tool.granularity import _STRUCTURAL_BLOCK_RE, parse_mixed_step_findings
from plan_tool.launcher import (
    apply_finding,
    escalate_to_split,
    revert_apply_if_parse_broken,
)
from plan_tool.response_contract import FINDINGS_RESPONSE_CONTRACT
from plan_tool import lessons
from plan_tool.lessons import (
    AppendLessonsResult,
    EquivalenceInvoker,
    LessonEntry,
    append_lessons,
    append_pending_lessons,
    load_lessons,
    parse_lessons_extract_response,
    render_lessons_block,
)
from plan_tool.model_response_sidecar import (
    ModelResponseSidecarOutcome,
    store_model_response_sidecar,
)
from plan_tool.parser import (
    ParseError,
    UnsupportedPlanFormatVersionError,
    ValidationError,
    _split_frontmatter,
    parse_body_sections,
    parse_plan,
    split_plan_document,
    write_plan,
)
from plan_tool.foundational_logic import (
    SweepInvoker,
    format_foundational_logic_block,
    run_foundational_logic_sweep,
    step_has_foundational_footprint,
)
from plan_tool.progress import ProgressReporter, StderrReporter
# Module-level (vs. lazy) so tests can monkeypatch these names on
# ``plan_tool.detail`` — same reason ``apply_finding`` is imported above.
# ``prompt_budget`` is a near-leaf (only imports ``style``) and ``telemetry``
# is a stdlib-only leaf, so neither creates an import cycle with ``detail``.
from plan_tool.prompt_budget import (
    PromptBudget,
    estimate_prompt_budget,
    maybe_warn_prompt_budget,
    render_budget_summary,
)
from plan_tool.context_window import active_context_window
from plan_tool.project_profile import (
    project_profile_context,
    render_project_context_block,
)
from plan_tool.telemetry import record_prompt_budget
from plan_tool.renderer import prompts_dir
from plan_tool.scenario_capture import (
    CATEGORY_FAILURE,
    CATEGORY_FOUNDATIONAL,
    CATEGORY_MIXED_STEP,
    PROMPT_MODE_EXPERIMENT,
    arm_from_split,
    capture_scenario,
    categorize_scenario,
    content_sha,
)
from plan_tool.prompt_excerpt import build_prompt_excerpt
from plan_tool.review import (
    HeuristicHit,
    _derive_file_path_symbols,
    _derive_symbols,
    _merge_candidate_symbols,
    heuristic_already_done,
    confidence_label,
    format_recommendation_for_apply,
)
from plan_tool.run_log import RunLogWriter, hash_prompt
from plan_tool.schema import (
    ChangeType,
    Complexity,
    Plan,
    Step,
    StepScope,
    StepStatus,
)
from plan_tool.shell import claude_invoke, suppress_prompt_budget_backstop
from plan_tool.split_safety import split_is_safe
from plan_tool.style import tool, warn


DetailInvoker = Callable[[str], str]
LessonsInvoker = Callable[[str], tuple[int, str]]

# Lesson surfaces relevant to authoring and critiquing a detail body:
# authoring rules plus the two cross-cutting clusters. create-heuristic /
# review-heuristic lessons don't apply to a detail artifact, so they're
# filtered out of both the detail prompts (the lessons-extraction prompt
# still sees all surfaces, so dedupe stays global).
_DETAIL_LESSON_SURFACES = frozenset(
    {"detail-authoring", "cross-step", "domain-shape"}
)

_MAX_PROMPT_FILE_BYTES = 4096


def render_declared_risk_context(plan: Plan) -> str:
    """Render advisory prompt context for an explicit risk declaration."""
    if plan.risk_profile is None or plan.risk_profile_rationale is None:
        return ""

    content = (
        "## Declared risk profile (advisory)\n\n"
        f"- Declared tier: `{plan.risk_profile.value}`\n"
        f"- Rationale: {plan.risk_profile_rationale}\n\n"
        "Treat this context as advisory. Keep the procedure proportionate to "
        "the declared risk profile. Keep existing grounding requirements, "
        "test duties, and safety review in force. If the work materially "
        "mismatches the declaration, explain the mismatch rather than treating "
        "the declaration as controlling policy."
    )
    return render_project_context_block(content)


# Surface + runnable structural remedies named in the detail prompt-budget
# advisory (the ``surface``/``remedies`` hints step 1's leaf renders).
_DETAIL_BUDGET_SURFACE = "detail"
_DETAIL_BUDGET_REMEDIES = (
    "author one step with --step N",
    "plan-tool split",
    "plan-tool scope-out",
)

# Required H2 section words for the detail response. Order doesn't matter;
# case is ignored. ``Deferred`` and ``References`` are intentionally NOT
# required even though the prompt/docs name optional sections — Input is
# conditional on consuming an existing contract, Deferred is omittable when
# there's nothing out of scope, and References is omittable when web search
# turns up no authoritative docs for the step. Rejecting thoughtful responses
# that drop any optional section would be worse than accepting them.
# ``acceptance criteria`` and ``table of contents`` are multi-word; we
# match the first token of the heading and trust the prompt to keep the
# trailing words consistent.
_REQUIRED_H2_TOKENS = (
    "summary",
    "table",
    "why",
    "files",
    "implementation",
    "tests",
    "acceptance",
)

# Display names used when synthesizing a stub heading for a single missing
# required section. Keeps the on-disk file readable for the next reader
# (``parse_detail_file_sections``, deep verifier) instead of leaving a
# bare ``## acceptance`` lowercased from the matcher tokens.
_REQUIRED_H2_DISPLAY = {
    "summary": "Summary",
    "table": "Table of Contents",
    "why": "Why",
    "files": "Files",
    "implementation": "Implementation",
    "tests": "Tests",
    "acceptance": "Acceptance criteria",
}

# Marker injected into a synthesized stub section so a human reading the
# detail file (or a future review pass) can tell the model omitted it.
# Kept short and grep-friendly so callers can audit how often this fires.
_STUB_SECTION_BODY = (
    "_(stub: model omitted this section — fill in manually)_\n"
)

# Match an H2 heading line: `## Why`, `## Why we did this`, `##  Files`.
# Captures the first significant token (lowercased) so the caller can
# check membership against ``_REQUIRED_H2_TOKENS``. ``[ \t]``, not ``\s`` —
# ``\s`` spans newlines, which would let a bare ``##`` line merge into the
# next real heading the same way it did in ``parser._real_h2_matches``.
_H2_HEADING_RE = re.compile(r"^##[ \t]+([A-Za-z]+)", re.MULTILINE)


def _matches_outside_fences(
    pattern: "re.Pattern[str]", text: str
) -> list["re.Match[str]"]:
    """``pattern.finditer(text)`` matches, excluding ones inside fenced code
    (every fenced span, including a trailing unmatched-to-EOF one — marker
    search never trusts that span as real text; see DETAIL_FORMAT.md rule
    3.1)."""
    fenced_spans = _fenced_code_spans(text).spans
    return [
        m
        for m in pattern.finditer(text)
        if not any(start <= m.start() < end for start, end in fenced_spans)
    ]


def _detail_response_body_start(lines: list[str]) -> Optional[int]:
    """Return the latest unfenced H1 before the first required H2."""
    text = "".join(lines)
    fenced_spans = _fenced_code_spans(text).spans
    span_index = 0
    latest_h1: Optional[int] = None
    offset = 0
    for i, line in enumerate(lines):
        while (
            span_index < len(fenced_spans)
            and offset >= fenced_spans[span_index][1]
        ):
            span_index += 1
        in_fence = (
            span_index < len(fenced_spans)
            and fenced_spans[span_index][0] <= offset < fenced_spans[span_index][1]
        )
        if not in_fence:
            if locate_detail_format_carrier(line) is not None:
                latest_h1 = i
            else:
                heading = _H2_HEADING_RE.match(line)
                if (
                    heading is not None
                    and heading.group(1).lower() in _REQUIRED_H2_TOKENS
                ):
                    return latest_h1
        offset += len(line)
    return None

# How many times ``generate_detail`` will call the invoker per step before
# giving up. Set to 2 (one retry) so a single transient parse failure —
# preamble before the H1, missing section, fenced wrapper that didn't get
# stripped — doesn't burn a step. Bumping higher invites runaway latency
# without much marginal recovery: if claude can't conform to the template
# after seeing the spec twice, the step's title/files probably need work.
_MAX_INVOKE_ATTEMPTS = 2

_DETAIL_DEFERRALS_MARKER = "plan-tool-detail-deferrals"
_DETAIL_DEFERRAL_STEPS_KEY = "detail_deferral_step_ids"
_DETAIL_DEFERRALS_RE = re.compile(
    r"\n?<!--\s*" + _DETAIL_DEFERRALS_MARKER
    + r"\s*\n(?P<payload>\{.*\})\s*\n-->\s*$",
    re.DOTALL,
)
# Matches only the marker's own opening line, without the greedy payload —
# used to locate the *last* non-fenced occurrence before running the full,
# end-anchored ``_DETAIL_DEFERRALS_RE`` from exactly that position. A bare
# ``.search()`` of the full regex is leftmost and DOTALL-greedy, so an
# earlier fenced example illustrating the envelope syntax would otherwise
# swallow everything through to the real trailing envelope as one invalid
# payload.
_DETAIL_DEFERRALS_MARKER_START_RE = re.compile(
    r"<!--\s*" + _DETAIL_DEFERRALS_MARKER + r"\s*\n"
)


def _find_real_deferrals_match(stripped: str) -> Optional["re.Match[str]"]:
    """Locate the trailing deferrals envelope, ignoring a fenced example.

    Shared by every reader of the envelope so a fix to this fence-exclusion
    logic doesn't have to be reapplied at each call site by hand.
    """
    marker_starts = _matches_outside_fences(_DETAIL_DEFERRALS_MARKER_START_RE, stripped)
    if not marker_starts:
        return None
    return _DETAIL_DEFERRALS_RE.match(stripped, marker_starts[-1].start())

# Checkpoint name template for per-step detail bodies. Two-digit step id
# keeps lexical sort of ``.plan-tool/checkpoints/<slug>/`` aligned with the
# numerical step order — matches the ``NN-<slug>.md`` convention used by
# the on-disk detail files themselves (``derive_detail_path``).
_DETAIL_CHECKPOINT_NAME = "detail-step-{step_id:02d}"

# Appended to the prompt on retry. Spells out exactly what the parser
# (``parse_detail_response``) needs so claude can self-correct without
# having to re-derive the contract from the original template. Keep this
# tight — it bolts onto an already-long prompt.
_REPROMPT_SUFFIX = (
    "\n\n---\n\n"
    "**Your previous response could not be parsed.** Re-emit the detail "
    "file with these constraints, no commentary about this notice:\n\n"
    "1. The very first character of the response must be `#` (the H1 "
    "title). No preamble, no apology, no ```` ``` ```` fences. If you "
    "genuinely cannot avoid adding text before or after the detail file "
    "(or wrapping it in a fence), bracket the file exactly between two "
    "lines — each alone on its own line, nothing else on it — "
    "`<!-- plan-tool:detail-response-start -->` before the `#` title and "
    "`<!-- plan-tool:detail-response-end -->` immediately after the last "
    "line of the file, before the deferrals envelope in point 5 (which "
    "always comes last, after the end marker, never inside it). Only the "
    "exact content between those two lines is read; nothing outside them "
    "is. Use each marker exactly once. If you also wrap the file in a "
    "fence and the file's own body contains a fenced code example, open "
    "your wrapping fence with four or more backticks (not three) so the "
    "body's own example can't be mistaken for your wrap's closer.\n"
    "2. All seven of these H2 headings must appear (any order, "
    "case-insensitive, trailing words allowed — `## Why we did this` "
    "satisfies `## Why`):\n"
    "   - `## Summary`\n"
    "   - `## Table of Contents`\n"
    "   - `## Why`\n"
    "   - `## Files` (e.g. `## Files (creates vs edits)`)\n"
    "   - `## Implementation`\n"
    "   - `## Tests`\n"
    "   - `## Acceptance criteria`\n"
    "3. If the step legitimately has no implementation work (a docs-only "
    "or verification-only step), keep the `## Implementation` heading "
    "and use the section body to describe the docs/verification work "
    "concretely — do not drop the heading.\n"
    "4. The line immediately after the H1 is reserved for plan-tool's own "
    "`plan-tool:detail-format-version` marker, stamped in after your "
    "response is parsed — leave it blank and do not write that marker "
    "yourself. `## Summary` is the first heading you write there (3-5 "
    "sentences for a reviewer skimming the file), followed by "
    "`## Table of Contents` (bulleted list of every H2 you emit, in "
    "document order, each line `- [<Section>](#<anchor>) — <one-line "
    "blurb>`).\n"
    "5. End with the required `<!-- plan-tool-detail-deferrals` JSON "
    "envelope, after `<!-- plan-tool:detail-response-end -->` if you used "
    "that marker in point 1 — it must be the true last thing in your "
    "response either way. It must contain exactly `deferrals`, an array "
    "of objects with `concept_id` and this step's integer `step_id`. Use "
    "an empty array when no signed-off concept is deferred.\n"
)

class DetailError(Exception):
    """Raised when the detail pipeline can't produce a usable result."""


def _reject_unmatched_plan_fence(plan_path: Path) -> None:
    """Stop detail publication before an unclosed plan fence truncates scope."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return
    if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
        raise DetailError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before authoring detail."
        )


# --- A/B prompt-mode text (combined = legacy default, split = lifted-out) ---
#
# COMBINED is the legacy behavior: the model does the foundational-logic grep
# inline and runs the purity self-check itself, with no separate sweep call.
# SPLIT omits both from authoring — a prior sweep supplies the finds, and the
# detail-quality pass owns purity. ``render_detail_prompt`` substitutes one set
# or the other so COMBINED output is byte-identical to the pre-split template.

# Combined: the model names + greps for shared logic itself (legacy bullet).
_DETAIL_FOUNDATIONAL_COMBINED_DIRECTIVE = """\
- Name this step's **foundational logic** — the core behavior or rule
  it adds or changes, stated in one phrase (a validation predicate, a
  parse routine, a dispatch branch). Then Grep the rest of the app for
  other locations that exercise the same logic — duplicated blocks,
  parallel call sites, sibling modules implementing the same rule.
  Surface every shared location **inside the existing detail-body
  sections, never under a new heading**: cite it in `## Implementation`
  (if this step should also change it), in `## Files (creates vs
  edits)` (if it belongs in this step's footprint), or in `##
  Deferred` (if left for another step, with the reason). A shared
  location that needs **consolidating into a single source to prevent
  side effects** requires a refactor/consolidation step `detail`
  cannot mint — route that find to `## Deferred` for reconcile rather
  than expanding this step's footprint. Apply the shared semantic-reach
  decision below before deciding whether a find belongs in this step.
  Use full repo-root-relative paths and symbolic anchors per the citation
  rules above."""

# Split: a prior sweep already found the shared locations; just place them.
_DETAIL_FOUNDATIONAL_SPLIT_DIRECTIVE = """\
- Fold the **Foundational-logic finds** above (if any) into the
  existing detail-body sections, **never under a new heading**: cite a
  shared location in `## Implementation` (if this step should also
  change it), in `## Files (creates vs edits)` (if it belongs in this
  step's footprint), or in `## Deferred` (if left for another step,
  with the reason). A find tagged for consolidation into a single
  source requires a refactor step `detail` cannot mint — route it to
  `## Deferred` for reconcile rather than expanding this step's
  footprint. Apply the shared semantic-reach decision below before
  deciding whether a find belongs in this step. Use full repo-root-relative
  paths and symbolic anchors per the citation rules above."""

# Combined: the always-on mixed refactor+feature self-check appended after the
# body. The single leading newline + the template's own newline before the
# placeholder reproduce the legacy blank line ahead of the heading.
_DETAIL_PURITY_SELF_CHECK_BLOCK = """
## Step purity self-check (mixed refactor + feature)

After writing the sections above, check the step you just detailed: does
your `## Implementation` describe *both* behavior-preserving restructuring
(a move / rename / extract that leaves behavior unchanged) *and* new or
changed behavior in code? That is a **mixed** step and should be two —
the make-the-change-easy refactor first, then the make-the-easy-change
feature.

Non-trigger: non-code elements (docs, config, CI) riding inside a code
step are not mixing; only refactor-vs-feature *in code* counts. A
`non-code` step is never mixed.

If — and only if — the step is mixed, append ONE extra block at the very
end of your response, after every section above:

```
## Structural findings

- MIXED-STEP: <one line — the behavior-preserving part, the
  behavior-changing part, and why they must be two steps>
```

The tool consumes this block separately to flag the step for splitting —
it is **not** part of the detail file. Emit it only when the step is
genuinely mixed; omit it entirely otherwise."""


def _render_foundational_finds_section(foundational_logic_block: str) -> str:
    """Split-mode context block listing the prior sweep's shared-location finds."""
    return (
        "\n### Foundational-logic finds (shared locations surfaced by a prior "
        "sweep)\n\n"
        "A separate sweep already named this step's foundational logic and "
        "grepped the\nrepo for other locations sharing it. Place each find "
        "into the right section\nbelow — do **not** re-run the search "
        "yourself.\n\n"
        f"{foundational_logic_block}\n"
    )


def _format_output_path_block(output_path: str) -> str:
    """Render the "plan-tool owns the write" instruction for the prompt.

    The subprocess runs under ``acceptEdits`` and must not author a detail
    file itself — plan-tool writes the captured response to the canonical
    path. ``output_path`` is the repo-relative path (empty string drops the
    path clause). Always leads with a blank line so it opens its own
    paragraph after the "respond with only the body" line; never a new H2.
    """
    path_clause = (
        f" to the canonical path `{output_path}`"
        if output_path
        else ""
    )
    return (
        "\n**Do not create, write, or edit any file.** plan-tool writes "
        f"the Markdown portion of your response{path_clause} — that is the "
        "only write. If "
        "you author a detail file yourself (e.g. at a path derived from "
        "your title), it lands beside the canonical file under a different "
        "slug and plan-tool archives it as an orphan. Emit the requested "
        "response and stop."
    )


def _concept_deferral_step_ids(node: object) -> tuple[int, ...]:
    metadata = getattr(node, "source_metadata", {})
    raw = metadata.get(_DETAIL_DEFERRAL_STEPS_KEY, "")
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ()
    if not isinstance(values, list) or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 1
        for value in values
    ):
        return ()
    return tuple(dict.fromkeys(values))


def derive_candidate_buckets(
    plan: Plan, plan_text: str
) -> dict[str, str]:
    """Return the body-section deferral candidates as ``concept_id -> section``.

    A detail step may defer any current plan body section (a *bucket*). The
    candidate set is derived fresh from the plan body with the same
    ``bootstrap_concepts`` recipe ``scope-review`` and ``create`` use, so a
    candidate's ``id`` (``concept_id(section.name, [])``) and its bucket/title
    (the normalized H2 name) match every other producer/consumer. Independent
    of any ``concepts.json`` on disk, so it works on a record-absent plan.
    """
    # ``concept_id`` depends only on the section name (empty parent path), so
    # the slug/fingerprint carried by the bootstrap tree never reaches the ids
    # we read back — a placeholder slug keeps this a pure body-derived map.
    sections = parse_body_sections(
        split_plan_document(plan_text).body, ignore_fenced_code=True
    )
    message = empty_concept_headings_message(sections)
    if message is not None:
        raise DetailError(message)
    bootstrap = bootstrap_concepts(
        plan,
        sections,
        plan_slug="candidate-buckets",
        plan_fingerprint="",
    )
    return {node.id: node.title for node in bootstrap.concepts}


def _format_concept_scope_block(
    plan: Plan,
    step: Step,
    concept_tree: Optional[ConceptTree],
    candidate_buckets: dict[str, str],
) -> str:
    approved_lines = _format_approved_concept_lines(plan, concept_tree)
    proposable_lines = [
        f"- `{bucket_id}` — {name} (proposable: defer this body section)"
        for bucket_id, name in sorted(
            candidate_buckets.items(), key=lambda item: item[1]
        )
    ]
    parts: list[str] = []
    if approved_lines:
        parts.append(approved_lines)
    if proposable_lines:
        parts.append(
            "Proposable body-section buckets (name a bucket's `id` in the "
            "envelope to record a pending `defer`):\n"
            + "\n".join(proposable_lines)
        )
    if not parts:
        return "_no reviewed concepts and no proposable body-section buckets_"
    return "\n\n".join(parts)


def _format_approved_concept_lines(
    plan: Plan,
    concept_tree: Optional[ConceptTree],
) -> str:
    if concept_tree is None:
        return ""
    owners: dict[str, list[int]] = {}
    for candidate in plan.steps:
        for concept_id in candidate.concept_ids:
            owners.setdefault(concept_id, []).append(candidate.id)
    lines: list[str] = []
    for node in sorted(
        concept_tree.concepts,
        key=lambda item: (item.order, item.parent_path, item.id),
    ):
        if node.review_state != "approved":
            continue
        owner_text = ",".join(str(value) for value in owners.get(node.id, [])) or "none"
        deferred_text = ",".join(
            str(value) for value in _concept_deferral_step_ids(node)
        ) or "none"
        lines.append(
            f"- `{node.id}` — {node.title}; decision={node.decision}; "
            f"owners={owner_text}; deferred_by={deferred_text}"
        )
    if not lines:
        return "_the concept record has no signed-off decisions_"
    return "\n".join(lines)


def _included_deferral_step_ids(
    concept_tree: Optional[ConceptTree], plan: Plan
) -> set[int]:
    if concept_tree is None:
        return set()
    known_steps = {step.id for step in plan.steps}
    affected: set[int] = set()
    for node in concept_tree.concepts:
        if node.review_state == "approved" and node.decision == "include":
            affected.update(
                step_id
                for step_id in _concept_deferral_step_ids(node)
                if step_id in known_steps
            )
    return affected


def _replace_detail_deferrals(
    concept_tree: ConceptTree,
    replacements: Sequence[tuple[int, tuple[DetailDeferral, ...]]],
) -> ConceptTree:
    """Return a copy with successful steps' links replaced in step order."""
    updated = copy.deepcopy(concept_tree)
    nodes = {node.id: node for node in updated.concepts}
    for step_id, deferrals in replacements:
        for node in updated.concepts:
            retained = [
                value
                for value in _concept_deferral_step_ids(node)
                if value != step_id
            ]
            if retained:
                node.source_metadata[_DETAIL_DEFERRAL_STEPS_KEY] = json.dumps(
                    retained, separators=(",", ":")
                )
            else:
                node.source_metadata.pop(_DETAIL_DEFERRAL_STEPS_KEY, None)
        for deferral in deferrals:
            node = nodes[deferral.concept_id]
            values = list(_concept_deferral_step_ids(node))
            values.append(step_id)
            node.source_metadata[_DETAIL_DEFERRAL_STEPS_KEY] = json.dumps(
                values, separators=(",", ":")
            )
    return updated


def _record_flat_deferrals(
    concept_tree: Optional[ConceptTree],
    deferrals: Sequence[DetailDeferral],
    candidate_buckets: dict[str, str],
    plan_path: Path,
    plan_fingerprint: str,
) -> ConceptTree:
    """Merge newly-deferred buckets into a flat, unreviewed decision record.

    Starts from an existing ``decision-record`` (preserved) or a fresh empty
    one when the plan carries no record. Each deferral becomes a flat
    ``ConceptNode(decision="defer", review_state="unreviewed", bucket=<section>)``
    — never signed off; ``scope-review`` is the sole signer. Collisions on a
    bucket id are resolved by the existing node: an *unreviewed* node already
    stands as the pending proposal, so it is a no-op (no duplicate); an
    *approved* node is the operator's authoritative decision and is left
    untouched (never re-opened to ``unreviewed``). A deferral for a bucket not
    in ``candidate_buckets`` is skipped defensively — the parse gate rejects it.
    """
    if (
        concept_tree is not None
        and concept_tree.record_kind == RECORD_KIND_DECISION
    ):
        record = copy.deepcopy(concept_tree)
    else:
        record = ConceptTree(
            plan_slug=_plan_slug(plan_path),
            plan_fingerprint="",
            concepts=[],
            record_kind=RECORD_KIND_DECISION,
        )
    existing_by_id = {node.id: node for node in record.concepts}
    next_order = max((node.order for node in record.concepts), default=-1) + 1
    for deferral in deferrals:
        if deferral.concept_id in existing_by_id:
            continue
        section = candidate_buckets.get(deferral.concept_id)
        if section is None:
            continue
        node = ConceptNode(
            id=deferral.concept_id,
            title=section,
            bucket=section,
            rationale=deferral.rationale,
            decision="defer",
            review_state="unreviewed",
            order=next_order,
        )
        record.concepts.append(node)
        existing_by_id[node.id] = node
        next_order += 1
    record.plan_fingerprint = plan_fingerprint
    return record


def _persist_concepts_or_mark_failed(
    plan_path: Path,
    tree: ConceptTree,
    results: "list[DetailResult]",
) -> "list[DetailResult]":
    """Publish ``tree``; on failure downgrade every written result with a reason.

    The detail file is already on disk when this runs, so a persistence failure
    leaves the body but no record — the reason says as much for recovery.
    """
    try:
        save_concepts(plan_path, tree)
    except (OSError, InvalidConceptTreeError, ValueError) as exc:
        return [
            replace(
                result,
                written=False,
                skipped_reason=(
                    f"concept deferral persistence failed: {exc} "
                    f"(detail written at {result.output_path}; prior "
                    "deferral links retained for recovery)"
                ),
            )
            if result.written else result
            for result in results
        ]
    return results


# Rendered in place of the already-implemented block under
# ``recovery_only`` — names the suppression rather than showing an empty
# result, so a reader of the rendered prompt can tell "skipped" apart from
# "scanned, found nothing" (the ordinary no-hits message from
# ``_format_already_implemented_block``).
_RECOVERY_SUPPRESSED_BLOCK_NOTE = (
    "_(skipped: direct recovery mode — no bundle detail file was read)_"
)


def render_detail_prompt(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    sibling_details: Sequence[Path] = (),
    plan_references_block: str = "",
    scope_fence_block: str = "",
    risk_context_block: str = "",
    foundational_logic_block: str = "",
    split_mode: bool = False,
    prior_body: str = "",
    output_path: Optional[Path] = None,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
    collect_blocks: Optional[list[tuple[str, int]]] = None,
    concept_tree: Optional[ConceptTree] = None,
    candidate_buckets: Optional[dict[str, str]] = None,
    project_context: Optional[str] = None,
    recovery_only: bool = False,
) -> str:
    """Render ``prompts/detail.md`` with full step context.

    ``output_path`` (when given, repo-relative or absolute) is named in the
    prompt as the canonical path plan-tool will write the response to, with
    an instruction **not** to write any file itself. The detail subprocess
    runs under ``--permission-mode acceptEdits`` and will otherwise author a
    detail file at a path derived from its own H1 title — a divergent slug
    (uncapped, so it keeps tokens :func:`derive_step_slug` truncates) that
    lands beside the canonical file and gets swept into ``archive/`` by
    :func:`_archive_orphan_details`. Pinning the path stops that orphan
    churn at the source.

    ``prior_body`` carries the folded members' **full** detail bodies when a
    merge re-authors the combined step (passed verbatim into
    ``${prior_body_block}`` with **no** ``max_file_bytes`` truncation — the
    distinct, faithful combine seam, not the truncating tone/structure-only
    ``${sibling_details_block}``). Empty for every non-merge call, where the
    section renders inert.

    Embeds the plan's metadata, the step (id/title/complexity/files/
    depends_on), declared file contents (truncated), any
    ``sibling_details`` (other detail files already on disk in the same
    ``plan-details/<slug>/`` directory) so claude can mirror tone /
    structure, the plan-level ``## References`` block (from the
    plan's prose body, populated by ``create``) so the step's References
    section can build on the existing list instead of re-researching
    from scratch, and the deterministic ``heuristic_already_done`` hits
    scoped to this step so claude can spot partially-implemented work
    before drafting.

    ``plan_references_block`` is the raw section body lifted from the
    plan; empty string when the plan has no References section, or when
    the section is just a ``_(TODO)_`` placeholder. The orchestrator
    builds this via :func:`extract_plan_references`; tests can pass
    a literal string.

    ``scope_fence_block`` carries both halves of the plan's scope fence —
    the plan's and this step's ``intent`` plus the guardrail sections —
    rendered by :func:`plan_tool.scope_fence.render_scope_fence`. Empty
    string renders the "no guardrails or scope fence" placeholder.

    ``recovery_only`` (default off) is the targeted-recovery signal from
    ``detail --recover-refused``: it skips ``already_implemented_block``'s
    :func:`_format_already_implemented_block` call, which otherwise scans
    *every* step's detail file (``heuristic_already_done``) and would raise
    ``DetailFormatError`` on an unrelated sibling's malformed marker before
    this step's own recovery could run. Callers also pass empty
    ``sibling_details`` under recovery so :func:`_format_sibling_details_block`
    reads none of the bundle's other files either.
    """
    template_path = prompts_dir() / "detail.md"
    template = Template(template_path.read_text(encoding="utf-8"))

    # Mode-conditional pieces. COMBINED (default): inline grep directive +
    # always-on self-check, no separate finds section — byte-identical to the
    # legacy template. SPLIT: a prior sweep's finds section + a place-the-finds
    # directive, and the self-check is dropped (detail-quality owns purity).
    if split_mode:
        finds_block = (
            foundational_logic_block.strip()
            or "_no shared foundational logic surfaced for this step_"
        )
        foundational_finds_section = _render_foundational_finds_section(
            finds_block
        )
        foundational_audit_directive = _DETAIL_FOUNDATIONAL_SPLIT_DIRECTIVE
        purity_self_check_block = ""
    else:
        foundational_finds_section = ""
        foundational_audit_directive = _DETAIL_FOUNDATIONAL_COMBINED_DIRECTIVE
        purity_self_check_block = _DETAIL_PURITY_SELF_CHECK_BLOCK

    # Build the content-bearing blocks once into locals so both the prompt and
    # (optionally) the budget breakdown reuse them — no second formatter pass.
    files_contents_block = _format_files_contents_block(
        step, repo_root, max_file_bytes=max_file_bytes
    )
    sibling_details_rendered = _format_sibling_details_block(
        sibling_details, max_file_bytes=max_file_bytes
    )
    prior_body_rendered = _format_prior_body_block(prior_body)
    plan_references_stripped = plan_references_block.strip()
    scope_fence_stripped = scope_fence_block.strip()
    already_implemented_rendered = (
        _RECOVERY_SUPPRESSED_BLOCK_NOTE
        if recovery_only
        else _format_already_implemented_block(plan, step, repo_root)
    )
    lessons_rendered = render_lessons_block(
        load_lessons(repo_root, surfaces=_DETAIL_LESSON_SURFACES)
    )
    concept_scope_rendered = _format_concept_scope_block(
        plan, step, concept_tree, candidate_buckets or {}
    )
    project_context_rendered = (
        project_profile_context(repo_root)
        if project_context is None
        else project_context
    )

    if collect_blocks is not None:
        # For the budget advisory's display breakdown; the leaf sorts by size,
        # so order is free. ``plan-references`` measures the stripped input, not
        # the substituted "_no plan-level references_" fallback.
        collect_blocks.extend([
            ("file-contents", len(files_contents_block.encode("utf-8"))),
            ("sibling-details", len(sibling_details_rendered.encode("utf-8"))),
            ("prior-body", len(prior_body_rendered.encode("utf-8"))),
            ("plan-references", len(plan_references_stripped.encode("utf-8"))),
            ("scope-fence", len(scope_fence_stripped.encode("utf-8"))),
            ("risk-context", len(risk_context_block.encode("utf-8"))),
            ("lessons", len(lessons_rendered.encode("utf-8"))),
            ("already-implemented",
             len(already_implemented_rendered.encode("utf-8"))),
            ("concept-scope", len(concept_scope_rendered.encode("utf-8"))),
        ])
        if project_context_rendered:
            collect_blocks.append(
                ("project-context", len(project_context_rendered.encode("utf-8")))
            )

    return template.safe_substitute(
        output_path_block=_format_output_path_block(
            _repo_relative(output_path, repo_root) if output_path else ""
        ),
        plan_title=plan.title,
        plan_status=plan.status.value,
        plan_priority=plan.priority.value,
        step_id=str(step.id),
        step_title=step.title,
        step_complexity=(step.complexity.value if step.complexity else "unknown"),
        step_depends_on=(
            ", ".join(str(d) for d in step.depends_on)
            if step.depends_on
            else "(none)"
        ),
        step_files_block=_format_step_files_block(step),
        change_type_directive_block=_format_tests_directive(
            step.change_type
        ),
        files_contents_block=files_contents_block,
        sibling_details_block=sibling_details_rendered,
        prior_body_block=prior_body_rendered,
        plan_references_block=(
            plan_references_stripped
            if plan_references_stripped
            else "_no plan-level references available_"
        ),
        scope_fence_block=(
            scope_fence_stripped
            if scope_fence_stripped
            else "_no plan-level guardrails or scope fence_"
        ),
        foundational_finds_section=foundational_finds_section,
        foundational_audit_directive=foundational_audit_directive,
        purity_self_check_block=purity_self_check_block,
        already_implemented_block=already_implemented_rendered,
        lessons_block=lessons_rendered,
        concept_scope_block=concept_scope_rendered,
        project_context_block=render_project_context_block(
            project_context_rendered
        ),
        risk_context_block=risk_context_block,
    )


def _detail_scenario_signals(step: Step, plan: Plan) -> dict[str, bool]:
    """Detect which A/B behaviors a detail authoring run exercised.

    Arm-independent by construction — derived from the step's declared ``files``
    /``creates`` and the plan's dependency STRUCTURE, never from the split-only
    sweep or the combined-only purity self-check — so the same (plan, step) tags
    the same way in either arm.
    - ``foundational-logic`` — the step has the shared-logic footprint (see
      :func:`step_has_foundational_footprint`).
    - ``mixed-step`` — the step participates in a refactor→feature ``depends_on``
      pair in its plan (the self-check axis: the combined arm runs the always-on
      purity check on this step, the split arm does not). Detecting the pair
      from plan structure makes this available even in split mode, where no
      authoring purity signal exists at capture time.
    """
    by_id = {s.id: s for s in plan.steps}
    feature_on_refactor = (
        step.change_type == ChangeType.FEATURE
        and any(
            by_id.get(d) is not None
            and by_id[d].change_type == ChangeType.REFACTOR
            for d in step.depends_on
        )
    )
    refactor_with_feature_dependent = (
        step.change_type == ChangeType.REFACTOR
        and any(
            s.change_type == ChangeType.FEATURE and step.id in s.depends_on
            for s in plan.steps
        )
    )
    return {
        CATEGORY_FOUNDATIONAL: step_has_foundational_footprint(step),
        CATEGORY_MIXED_STEP: feature_on_refactor or refactor_with_feature_dependent,
    }


def _render_step_sweep_context(step: Step, scope_fence_block: str) -> str:
    """Render one step as scope for the foundational-logic sweep (detail).

    The sweep names *this step's* foundational logic and greps for other
    locations sharing it. The per-step fence supplies the focused property and
    enforcement boundary before the sweep classifies a shared location.
    """
    files = ", ".join(step.files) if step.files else "(none)"
    creates = ", ".join(step.creates) if step.creates else "(none)"
    fence = scope_fence_block.strip() or "_no plan-level guardrails or scope fence_"
    return (
        f"Step {step.id}: {step.title}\n"
        f"  files: {files}\n"
        f"  creates: {creates}\n\n"
        "Focused property and enforcement boundary:\n\n"
        f"{fence}"
    )


def render_detail_quality_prompt(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    detail_body: str,
    plan_guardrails_block: str = "",
    risk_context_block: str = "",
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
    project_context: Optional[str] = None,
) -> str:
    """Render ``prompts/detail-quality.md`` for one step's detail body.

    Reuses the same per-step block formatters as
    :func:`render_detail_prompt` (``_format_step_files_block`` for the
    declared files list, ``_format_files_contents_block`` for truncated
    file bodies) so the review prompt sees the exact same source-of-truth
    inputs the authoring prompt saw. ``detail_body`` is the freshly-
    written prose to review — substituted into ``${detail_body_block}``
    verbatim after stripping leading/trailing whitespace.
    """
    template_path = prompts_dir() / "detail-quality.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    project_context_rendered = (
        project_profile_context(repo_root)
        if project_context is None
        else project_context
    )
    return template.safe_substitute(
        plan_title=plan.title,
        step_id=str(step.id),
        step_title=step.title,
        step_complexity=(step.complexity.value if step.complexity else "unknown"),
        step_depends_on=(
            ", ".join(str(d) for d in step.depends_on)
            if step.depends_on
            else "(none)"
        ),
        step_files_block=_format_step_files_block(step),
        change_type_directive_block=_format_tests_directive(
            step.change_type
        ),
        files_contents_block=_format_files_contents_block(
            step, repo_root, max_file_bytes=max_file_bytes
        ),
        detail_body_block=detail_body.strip(),
        plan_guardrails_block=(
            plan_guardrails_block.strip()
            if plan_guardrails_block.strip()
            else "_no plan-level guardrails or scope fence_"
        ),
        lessons_block=render_lessons_block(
            load_lessons(repo_root, surfaces=_DETAIL_LESSON_SURFACES)
        ),
        project_context_block=render_project_context_block(
            project_context_rendered
        ),
        risk_context_block=risk_context_block,
        findings_response_format_block=FINDINGS_RESPONSE_CONTRACT.render_prompt_block(),
    )


# Deterministic primitives surfaced per-step in the convergence loop.
# ``detail-body`` is apply-eligible; the rest are structural diagnostics
# triage defers (path drift / unresolved paths the body-only LLM review
# can't see). All run without a claude call.
_DETAIL_GROUNDING_SOURCES = frozenset(
    {"file-check", "files-coherence", "detail-coverage", "detail-body"}
)


def _apply_eligible_ids(
    findings: "list[Recommendation]",
    *,
    triage: bool,
    include_info: bool,
) -> frozenset[str]:
    """IDs of the apply-eligible subset — the findings the loop can drive
    to zero. Convergence is measured over these only; deferred structural
    findings (which the loop never resolves) would otherwise inflate
    ``is_marginal``'s overlap and stop the loop early."""
    from plan_tool.review import partition_findings_for_triage
    open_apply, _ = partition_findings_for_triage(
        findings, triage_enabled=triage, include_info=include_info
    )
    return frozenset(r.id for r in open_apply)


def _merge_findings(*groups: "list[Recommendation]") -> "list[Recommendation]":
    """Concatenate finding lists, deduping by stable rec id (first wins)."""
    seen: set[str] = set()
    out: list["Recommendation"] = []
    for group in groups:
        for rec in group:
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)
    return out


_ADVISORY_ALTITUDE_BLOCK_RE = re.compile(
    r"^#{1,6}\s*Advisory altitude findings\s*$\n?(.*?)(?=^#{1,6}\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_ADVISORY_ALTITUDE_BULLET_RE = re.compile(
    r"^\s*[-*]\s*(?:(?:\*\*)?ALTITUDE(?:\*\*)?\s*[:\-]\s*)?(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_advisory_altitude_findings(
    raw: str, step: Step
) -> list["Recommendation"]:
    """Lift detail-quality conceptual-altitude bullets into advisory recs.

    These findings are deliberately outside the normal ``## Findings`` lane:
    they are visible to the operator, but ``detail-altitude`` is not
    apply-eligible because demoting over-prescriptive prose needs judgment.
    """
    from plan_tool.review import (
        DETAIL_ALTITUDE_SOURCE,
        Recommendation,
        _make_rec_id,
    )

    out: list["Recommendation"] = []
    for block in _ADVISORY_ALTITUDE_BLOCK_RE.finditer(raw):
        for bullet in _ADVISORY_ALTITUDE_BULLET_RE.finditer(block.group(1)):
            body = bullet.group(1).strip()
            if not body or body.lower() == "_(none)_":
                continue
            out.append(
                Recommendation(
                    id=_make_rec_id(step.id, DETAIL_ALTITUDE_SOURCE, body),
                    source=DETAIL_ALTITUDE_SOURCE,
                    severity="info",
                    step_id=step.id,
                    title=body.splitlines()[0][:120],
                    body=body,
                    suggested_action=None,
                )
            )
    return out


def collect_step_grounding_findings(
    plan: Plan,
    plan_path: Path,
    step: Step,
    *,
    repo_root: Path,
    plan_name: str,
) -> list["Recommendation"]:
    """Per-step deterministic grounding findings, scoped to ``step``.

    Best-effort: ordinary review-primitive failures yield ``[]`` — a
    supplement, never a gate. A present unsupported detail is the deliberate
    hard-refusal exception. Filtered to :data:`_DETAIL_GROUNDING_SOURCES`."""
    from plan_tool.review import collect_deterministic_findings
    try:
        det = collect_deterministic_findings(
            plan,
            plan_path,
            repo_root=repo_root,
            plan_name=plan_name,
            step_filter=step.id,
        )
    except DetailFormatError:
        raise
    except Exception:
        return []
    return [
        rec for rec in det
        if rec.source in _DETAIL_GROUNDING_SOURCES and rec.step_id == step.id
    ]


def _iteration_prefix(
    step_id: int, iteration: int, max_iterations: int, phase: str
) -> str:
    """Build the convergence loop's structured progress prefix.

    Shape: ``step 8 / iter 2-of-3 / scan`` — the step, the iteration
    position against the loop's budget, and the current phase, joined so an
    operator reads the whole position off any single progress line. The
    ``iter`` segment is dropped when ``iteration`` is 0 (one-shot probe) or
    ``max_iterations`` is unknown (``<= 0``), leaving ``step 8 / scan``.
    The ``phase`` itself may carry its own ``A-of-B`` budget (e.g.
    ``apply 1-of-3``) — the caller composes that string.

    The loop runs one trailing audit *after* the final apply round to
    confirm whether it converged and count any findings still open for the
    stop report (the caller passes ``state.iteration + 2``, which reaches
    ``max_iterations + 1`` only on that terminal pass — it opens no further
    apply round). It carries no round number: ``iter 4-of-3`` implies a
    forbidden fourth round, and pinning it to ``iter N-of-N`` collides with
    the real opening scan of round N (the round-N opener and its post-apply
    audit are distinct passes). So a pass past the cap is named for its job
    — ``step 8 / convergence check`` — rather than numbered.
    """
    if iteration and max_iterations > 0:
        if iteration > max_iterations:
            return f"step {step_id} / convergence check"
        return f"step {step_id} / iter {iteration}-of-{max_iterations} / {phase}"
    return f"step {step_id} / {phase}"


@dataclass(frozen=True)
class DeferralReport:
    """How the convergence loop should surface one iteration's deferred set.

    ``collapsed`` is True when the deferred id set is identical to the
    previously-reported one — the loop prints the single ``line`` (a delta
    summary) instead of re-running the full per-finding
    :func:`review.emit_triage_summary` block. When False, the loop prints
    the full block; ``line`` then carries a one-line delta note (added /
    resolved ids) to append after it, or ``""`` on the first reported
    iteration when there's no prior set to diff against.
    """

    collapsed: bool
    line: str


def summarize_deferral_delta(
    deferred: "list[Recommendation]",
    *,
    previous_ids: Optional[frozenset[str]],
    previous_iteration: int,
) -> DeferralReport:
    """Decide how to surface an iteration's triage-deferred findings.

    The convergence loop re-runs the triage partition every iteration, and
    the deferred set is usually stable across iterations — structural
    diagnostics (path drift, unresolved paths) that the body-only apply
    pass can never resolve. Reprinting the full multi-line block on every
    pass buries the apply progress operators actually want to read.

    When ``deferred``'s id set equals ``previous_ids`` (the last reported
    set), return ``collapsed=True`` carrying a one-line summary —
    ``deferred findings unchanged from iter N (2: id-a, id-b)`` — so the
    caller skips the full block. When the set changed and there is a prior
    set, return ``collapsed=False`` with ``line`` set to a delta note
    (``+added / -resolved`` ids) the caller appends after the full block.
    The first reported iteration (``previous_ids is None``) returns
    ``collapsed=False`` with an empty ``line`` — full block, nothing to
    diff.

    Display preserves the finding order in ``deferred``; the added/resolved
    diff is sorted for stable output.
    """
    current_ids = frozenset(rec.id for rec in deferred)
    ordered_ids = [rec.id for rec in deferred]
    if previous_ids is not None and current_ids == previous_ids:
        return DeferralReport(
            collapsed=True,
            line=(
                f"deferred findings unchanged from iter {previous_iteration} "
                f"({len(deferred)}: {', '.join(ordered_ids)})"
            ),
        )
    if previous_ids is None:
        return DeferralReport(collapsed=False, line="")
    added = sorted(current_ids - previous_ids)
    resolved = sorted(previous_ids - current_ids)
    notes: list[str] = []
    if added:
        notes.append(f"+{', '.join(added)}")
    if resolved:
        notes.append(f"-{', '.join(resolved)}")
    return DeferralReport(
        collapsed=False,
        line=(
            f"deferred set changed from iter {previous_iteration} "
            f"({'; '.join(notes)})"
        ),
    )


def emit_detail_findings_summary(
    findings: "list[Recommendation]",
    *,
    step_id: int,
    iteration: int,
    stream=None,
) -> None:
    """Stream a severity-tagged summary of a detail-quality scan's findings.

    Mirrors the completeness-audit display so a `detail` convergence loop
    reads the same as a `completeness-audit`: a one-line severity histogram
    (:func:`review._render_severity_banner`, the audit's ``Findings:`` banner)
    followed by one ``- SEVERITY [anchor]: body`` line per gap, most-urgent
    first. Without this the loop only showed the scan completing and a single
    truncated apply-finding title — the operator couldn't see *what* was found
    or *how severe*. No-op on an empty scan: the loop's existing
    ``converged (0 findings)`` line already names that case.
    """
    if not findings:
        return
    # Resolve stderr at call time, not as a default arg — a ``sys.stderr``
    # default binds at definition and bypasses capsys / any later rebind.
    if stream is None:
        stream = sys.stderr
    from plan_tool.review import (
        _SEVERITY_BANNER_ORDER,
        _render_severity_banner,
    )

    banner = _render_severity_banner(findings)
    print(
        f"        detail-quality: step {step_id} / iter {iteration} — {banner}",
        file=stream,
    )
    rank = {lvl: i for i, lvl in enumerate(_SEVERITY_BANNER_ORDER)}
    for rec in sorted(
        findings, key=lambda r: (rank.get(r.severity, len(rank)), r.id)
    ):
        tag = f" [{rec.anchor}]" if rec.anchor else ""
        # Collapse the body to a single line — the audit renders the full
        # finding (not the 120-char-clipped title) so an over-long gap doesn't
        # read truncated mid-thought; newlines would break the one-per-line list.
        body = " ".join((rec.body or rec.title).split())
        print(
            f"          - {rec.severity.upper()}{tag}: {body} "
            f"[{confidence_label(rec.confidence)}]",
            file=stream,
        )


def _emit_split_recommendations(
    recs: "list[Recommendation]",
    *,
    plan_slug: str,
    stream=None,
) -> None:
    """Render the bridge's recommend-only ``structural-split`` findings.

    These come from ``escalate_to_split`` on the unattended / non-opt-in
    path: a flagged mixed step the operator must split through a
    session-directed edit via
    ``plan-tool split``. The message is single-sourced through
    :func:`review.triage_reason` (same ``structural-split`` text the
    convergence loop's triage rollup uses), but the header is honest about
    being a post-loop, act-on-this surface — unlike
    ``review.emit_triage_summary``'s loop-short-circuit preamble, which is
    wrong here (a default, non-``--iterate`` run has no loop).
    """
    if not recs:
        return
    # Resolve stderr at call time, not as a default arg — a ``sys.stderr``
    # default binds at definition and bypasses capsys / any later rebind.
    if stream is None:
        stream = sys.stderr
    from plan_tool.review import triage_reason

    print(
        f"        structural splits for {plan_slug} — act on these with "
        "`plan-tool split` (no auto-apply):",
        file=stream,
    )
    for rec in recs:
        print(
            f"          - {rec.title} [{confidence_label(rec.confidence)}]",
            file=stream,
        )
        print(f"              {triage_reason(rec)}", file=stream)
        if rec.body:
            print(f"              {rec.body}", file=stream)
        if rec.suggested_action is not None:
            print(f"              {rec.suggested_action}", file=stream)


def collect_detail_quality_findings(
    plan_path: Path,
    step: Step,
    *,
    repo_root: Path,
    plan_name: str,
    invoker: DetailInvoker,
    iteration: int = 0,
    max_iterations: int = 0,
    reporter: Optional[ProgressReporter] = None,
    run_logger: Optional[RunLogWriter] = None,
    return_status: bool = False,
    project_context: Optional[str] = None,
    risk_context_block: str = "",
) -> "list[Recommendation] | tuple[list[Recommendation], bool]":
    """Invoke claude with ``prompts/detail-quality.md``, lift the
    ``## Findings`` block into ``Recommendation`` objects, and merge in
    the deterministic per-step grounding findings
    (:func:`collect_step_grounding_findings`).

    ``return_status`` (opt-in, default off so this stays a pure addition)
    switches the return to ``(findings, succeeded)`` for the purity cache
    helper's write-gate. ``succeeded`` is True iff the raw response reached
    the mandatory final ``## Findings`` heading (see
    :func:`_response_reached_findings`) — the marker that tells a
    genuinely-pure reply (reached ``## Findings``, omitted ``## Structural
    findings``) apart from a failed / truncated / no-detail-quiet-probe reply,
    all three of which yield the *same* empty purity subset. A direct caller
    that leaves ``return_status`` off gets the bare list unchanged.

    Re-reads the detail file on every call (rather than threading an
    in-memory body through) so iteration N+1's review runs against
    iteration N's apply-output, which lives on disk. Returns ``[]`` when
    the step has no ``detail`` pointer or the referenced file is
    missing — both conditions short-circuit before any claude call so
    callers can use this as a quiet probe.

    ``_claude_recommendations`` is lazy-imported here to keep
    ``plan_tool.review`` out of detail's module-load graph (review
    transitively imports launcher → parser → schema — a cycle if review
    is hoisted to the top of detail.py).

    ``iteration`` / ``max_iterations`` drive the structured progress
    prefix (when ``reporter`` is provided) so operators read each scan's
    iteration position off any single line — ``step 8 / iter 2-of-3 /
    scan``. The initial discovery scan is iteration 1 and the loop's
    re-scans count up from there (the caller applies the +2 offset so they
    don't collide); ``max_iterations`` is the loop's budget cap (the
    ``-of-N`` denominator). ``iteration=0`` (the default) renders no
    iteration position, for one-shot probe callers. Neither is folded into
    any hash today because the apply path edits the detail file in place,
    so iteration N+1's review naturally runs against iteration N's
    apply-output without replay risk.

    ``reporter`` opts the silent claude call into the same start +
    heartbeat lines that ``generate_detail``'s main call and the
    lessons-distill call emit. ``None`` (the default) keeps the original
    quiet-probe behavior for callers that just want recommendations.

    ``risk_context_block`` is an explicit passthrough, not computed here —
    this function also backs the completeness-audit's read-through purity
    check, which must stay unaffected by a declared risk profile.
    """
    from plan_tool.review import _claude_recommendations  # lazy: see docstring

    plan = parse_plan(plan_path)
    detail_path = repo_root / step.detail if step.detail else None
    if detail_path is None or not detail_path.is_file():
        return ([], False) if return_status else []
    detail_body = detail_path.read_text(encoding="utf-8")
    require_supported_detail_format_version(detail_body, path=detail_path)
    if not detail_body.strip():
        return ([], False) if return_status else []
    prompt = render_detail_quality_prompt(
        plan,
        step,
        repo_root=repo_root,
        detail_body=detail_body,
        plan_guardrails_block=extract_plan_guardrails(plan_path),
        risk_context_block=risk_context_block,
        project_context=project_context,
    )
    # Log the quality-audit Claude call so a run log can price each
    # iteration's re-scan (previously invisible — only the main authoring
    # call was logged). ``bind_shell_sink`` makes the shell invoker emit the
    # paired ``claude_call_end``, same as ``generate_detail``'s authoring call.
    if run_logger is not None:
        run_logger.claude_call_start(
            phase="detail_quality_audit",
            attempt=1,
            prompt_bytes=len(prompt.encode("utf-8")),
            prompt_sha256=hash_prompt(prompt),
            step_id=step.id,
        )
        qa_sink = run_logger.bind_shell_sink(
            phase="detail_quality_audit", attempt=1,
        )
    else:
        qa_sink = contextlib.nullcontext()
    if reporter is not None:
        prefix = _iteration_prefix(step.id, iteration, max_iterations, "scan")
        handle = reporter.start_step(
            1, 1, f"iterate step {step.id}: scanning for findings",
            prefix=prefix,
        )
        start = time.monotonic()
        with qa_sink:
            raw = invoker(prompt)
        elapsed = time.monotonic() - start
        # Close on the same signal the purity cache write-gates on: a reply that
        # never reached ``## Findings`` produced no verdict, so closing it
        # ``done`` (and, after a transient retry notice, "recovered after N
        # retries") claims coverage the scan never delivered. See BUG_BACKLOG.
        reason = _detail_quality_failure_reason(raw)
        if reason is None:
            handle.complete(elapsed, len(raw.encode("utf-8")))
        else:
            handle.fail(elapsed, reason)
    else:
        with qa_sink:
            raw = invoker(prompt)
    # Fold the deterministic per-step grounding findings in alongside the
    # LLM's: every loop caller goes through here, so the supplement rides
    # the same monkeypatch seam and convergence accounting.
    purity = parse_mixed_step_findings(raw, step, plan_name)
    # Strip the structural block BEFORE the ``## Findings`` parse.
    # ``parse_finding_bullets`` slices from the last ``## Findings`` heading
    # to end-of-string and deliberately keeps trailing ``##`` sub-blocks in
    # the finding body (reconcile's ``## Decision``), so a ``## Structural
    # findings`` block following ``## Findings`` would otherwise be absorbed
    # into the last real finding's body. Removing it here makes that leak
    # impossible regardless of where the model places the block.
    raw_for_findings = _STRUCTURAL_BLOCK_RE.sub("", raw)
    # Same defensive strip for advisory altitude blocks: these are parsed
    # into source="detail-altitude" below and must not be absorbed into a
    # normal apply-eligible source="claude" recommendation when the model
    # places the block after ``## Findings``.
    altitude = parse_advisory_altitude_findings(raw, step)
    raw_for_findings = _ADVISORY_ALTITUDE_BLOCK_RE.sub("", raw_for_findings)
    merged = _merge_findings(
        _claude_recommendations(raw_for_findings),
        altitude,
        collect_step_grounding_findings(
            plan, plan_path, step, repo_root=repo_root, plan_name=plan_name
        ),
        purity,
    )
    if return_status:
        return merged, _response_reached_findings(raw)
    return merged


def _response_reached_findings(raw: str) -> bool:
    """True iff a detail-quality response reached the mandatory final
    ``## Findings`` heading — the purity cache write-gate's success signal.

    ``prompts/detail-quality.md`` requires ``## Findings`` as the final section
    of every well-formed reply but tells the model to *omit* ``## Structural
    findings`` for a type-pure step. So keying on ``## Findings`` (not
    ``## Structural findings``) caches a genuinely-pure reply — which reaches
    ``## Findings`` yet emits no purity bullet — while still rejecting a
    truncated/garbled reply cut off before ``## Findings`` (and the empty-raw
    failed-invoke and no-detail quiet-probe cases, which never reach it).
    ANSI-stripped like ``parse_finding_bullets`` so a colorized reply still
    matches. Single-sources the launcher's heading regex to avoid drift.

    Known edge (accepted, low-risk — see BACKLOG): a reply that *echoes* the
    prompt's section headers, or is truncated in a way that surfaces
    ``## Findings`` without the model actually completing its analysis, would
    read as succeeded. In practice ``## Findings`` is the *last* required
    section (after ``## Structural findings``), so reaching it normally implies
    the analysis completed; hardening against an echoing/reordering reply (e.g.
    requiring the marker at end-of-text, or a structured envelope) is tracked as
    a below-floor/success-gate hardening follow-up rather than solved here.
    """
    from plan_tool.launcher import _ANSI_RE, _FINDINGS_HEADING_RE

    return _FINDINGS_HEADING_RE.search(_ANSI_RE.sub("", raw)) is not None


def _detail_quality_failure_reason(raw: str) -> Optional[str]:
    """Why a detail-quality reply produced no verdict, or ``None`` when it did.

    Keys on :func:`_response_reached_findings` — the purity cache's write-gate —
    so the progress line and the cache agree on what counts as a real scan (a
    genuinely-pure reply still reaches ``## Findings``). The empty case is split
    out because it is the common one: a timed-out call returns ``""``.
    """
    if not raw.strip():
        return f"empty response ({len(raw.encode('utf-8'))} bytes)"
    if not _response_reached_findings(raw):
        return (
            "truncated response: no `## Findings` section "
            f"({len(raw.encode('utf-8'))} bytes)"
        )
    return None


def _impl_tests_section_text(detail_body: str) -> str:
    """Concatenate a detail body's ``## Implementation`` + ``## Tests`` text.

    The single source both step 3's cache write-back and step 4's below-floor
    magnitude diff route through, so the two sides of the diff concatenate the
    same sections in the same order with the same separator.

    Section tokens are the heading's first significant word, so a
    gate-nonconformant tests heading on disk (``## Testing`` → ``testing``,
    ``## Test coverage`` → ``test``) would miss a bare ``get("tests")`` and
    return empty — which the below-floor grader must never read as "no change."
    Match the known aliases so a Tests-only rewrite under such a heading is still
    measured; if none resolve the result is empty and the grader treats that as
    unmeasurable → a genuine miss (see ``_grade_purity_cache_miss``).
    """
    sections = parse_detail_file_sections(detail_body)

    def _first(*tokens: str) -> str:
        for tok in tokens:
            if sections.get(tok):
                return sections[tok]
        return ""

    return (
        _first("implementation", "impl")
        + "\n"
        + _first("tests", "test", "testing")
    )


# Type of the audit path's below-floor reuse hook: given the loaded (stale)
# entry plus the current step's freshly-computed identity/components and
# concatenated Implementation/Tests text, return the reuse verdict (skip Claude)
# or ``None`` to fall through to the normal miss (Claude call + write-back).
BelowFloorReuse = Callable[..., "Optional[list[Recommendation]]"]


def _cached_purity_findings(
    plan_path: Path,
    step: Step,
    *,
    repo_root: Path,
    plan_name: str,
    invoker: DetailInvoker,
    read_through: bool,
    iteration: int = 0,
    max_iterations: int = 0,
    reporter: Optional[ProgressReporter] = None,
    run_logger: Optional[RunLogWriter] = None,
    below_floor_reuse: "Optional[BelowFloorReuse]" = None,
    return_status: bool = False,
    project_context: Optional[str] = None,
) -> "list[Recommendation] | tuple[list[Recommendation], bool]":
    """Cache boundary around :func:`collect_detail_quality_findings`'s
    expensive MIXED-STEP purity verdict, keyed by step 1's
    :func:`plan_tool.fingerprint.compute_purity_cache_key`. Drop-in for the
    producer (same inputs + ``read_through``, same merged-list return).

    ``return_status=True`` mirrors the producer: returns
    ``(findings, succeeded)`` so the audit collector can tell a failed scan
    (timeout / empty / truncated) from a genuinely-pure empty verdict.

    ``read_through`` selects the mode:

    - **``True`` — the audit path only** (``completeness_phases``'s
      ``_collect_purity_split_findings``): on a hit (an entry whose stored key
      equals the freshly computed key) the cached purity verdict is reused and
      the Claude call is skipped; the cheap deterministic grounding is
      recomputed fresh and merged in. On a miss it calls Claude and, on
      success, writes the verdict back — never with a declared risk profile
      in the prompt (the completeness audit's non-goal). An entry whose
      ``risk_context_rendered`` is ``True`` (a write-through call produced it
      under a declared profile) is unusable here on both reuse paths even on
      a key match, so it can't leak a risk-influenced verdict through the
      shared cache.
    - **``False`` — the detail-authoring loop** (``generate_detail``'s two
      sites): *always* calls Claude (write-through) and refreshes the cache on
      success — it never skips. This is load-bearing, **not** a tunable: the
      single Claude call also emits apply-eligible ``## Findings``
      semantic-grounding recs that Read/Grep files *outside* ``step.all_files``,
      which the cache key cannot cover. The audit path discards those grounding
      recs (it keeps only the ``granularity-split`` purity subset), so a hit is
      lossless there; the detail loop drives its apply against them every pass,
      so skipping would silently drop grounding-against-current-code. Do not
      "optimize" the detail loop into ``read_through=True``.

    ``below_floor_reuse`` is the audit path's step-4 (BACKLOG #144) hook,
    consulted **only on a read-through miss with a loaded entry, before Claude
    is called**: it is handed the stale entry plus the current step's
    freshly-computed components / detail relpath / concatenated
    ``## Implementation`` + ``## Tests`` text and returns a reuse verdict when
    the miss is a *trivial* edit (below the 0.5% Impl/Tests floor with no
    frontmatter/identity change), or ``None`` for a genuine miss. A trivial
    reuse returns that verdict and skips Claude — and, per decision 3a, writes
    nothing, so the stored baseline stays at the last *real* check (a run of
    individually-sub-floor edits accumulates against a fixed baseline and
    re-checks once their sum crosses the floor). The two authoring sites pass
    no hook, so they always fall through to Claude.

    The write is **success-gated on the invoke signal, never on list-emptiness**
    (decision 3a): a failed invoke, a no-detail quiet-probe, and a
    truncated/garbled reply all yield the same empty purity subset, so only the
    producer's ``succeeded`` bool can tell a genuinely-pure ``[]`` from a
    non-verdict ``[]``. A false ``succeeded`` writes nothing and re-checks next
    audit. The producer is called as a module global so the suites' existing
    ``plan_tool.detail.collect_detail_quality_findings`` monkeypatch still
    intercepts the Claude call.
    """
    from plan_tool.fingerprint import compute_purity_cache_key
    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
    from plan_tool.purity_cache import (
        PurityCacheEntry,
        load_purity_cache,
        purity_cache_path,
        save_purity_cache,
    )
    from plan_tool.review_persistence import _utc_now_iso

    def _finish(
        findings: list, succeeded: bool,
    ) -> "list | tuple[list, bool]":
        return (findings, succeeded) if return_status else findings

    plan = parse_plan(plan_path)
    cache_path = purity_cache_path(repo_root, _plan_slug(plan_path))
    # Prune orphaned entries on every load: the plan is already parsed, so pass
    # its step ids so a split/merge/scope-out that drops a step doesn't leave its
    # cache entry accreting unbounded (decision 3's "prune on load").
    valid_ids = {s.id for s in plan.steps}
    combined_key, components = compute_purity_cache_key(
        plan, plan_path, step, repo_root
    )
    # Load (and prune) once; the hit test and the write-back below both reuse it,
    # so a miss doesn't parse <slug>.json twice. The repo mutation lock serializes
    # writers, so no concurrent write can stale this snapshot before save.
    cache = load_purity_cache(cache_path, valid_step_ids=valid_ids)

    # Read fresh off the ``plan`` this function already re-parsed above. The
    # read-through caller (the completeness-audit's purity check) must never
    # render a declared risk profile; the write-through (detail-authoring
    # loop) callers are the only ones that should. Computed once here so the
    # hit/reuse gate below and the producer call further down agree on
    # exactly what this call renders.
    risk_context_block = "" if read_through else render_declared_risk_context(plan)

    if read_through:
        entry = cache.entries.get(step.id)
        # An entry a write-through call produced under a declared risk
        # profile is unusable here on EITHER reuse path below: the audit's
        # own miss-path call always renders an empty risk context, so
        # serving it a verdict Claude produced under risk-profile framing
        # would silently violate that invariant even though the cache key
        # itself still matches (the key covers file/detail/frontmatter
        # inputs, not risk context).
        usable = entry is not None and not entry.risk_context_rendered
        if usable and entry.cache_key == combined_key:
            # Hit: return the cached purity verdict alone. The only read-through
            # caller (`_collect_purity_split_findings`) keeps just the
            # GRANULARITY_SPLIT_SOURCE subset and discards deterministic grounding
            # and change-type findings, so recomputing them here would be work
            # thrown away. (The detail-authoring loop that *does* consume the full
            # set never read-throughs — it runs write-through, always calling
            # Claude — so no caller is served stale grounding by this shortcut.)
            return _finish(
                _tag_purity_verdict_provenance(entry.findings, "exact-cache"),
                True,
            )
        # Graded miss (BACKLOG #144): with a loaded entry the audit caller's
        # hook can reuse the cached verdict on a *trivial* edit (below the
        # Impl/Tests floor, no frontmatter/identity change) — no Claude, no
        # write. A genuine miss (or no hook) falls through to the call below.
        if usable and below_floor_reuse is not None:
            detail_body = _read_step_detail_body(plan, plan_path, step, repo_root)
            reuse = below_floor_reuse(
                entry=entry,
                step=step,
                current_components=components,
                current_detail_relpath=_step_detail_relpath(
                    plan, plan_path, step, repo_root
                ),
                current_impl_tests_text=_impl_tests_section_text(detail_body),
            )
            if reuse is not None:
                return _finish(reuse, True)

    # Miss (audit path) or always (detail-authoring path): call the real
    # producer with the success signal, then success-gate the write.
    result = collect_detail_quality_findings(
        plan_path,
        step,
        repo_root=repo_root,
        plan_name=plan_name,
        invoker=invoker,
        iteration=iteration,
        max_iterations=max_iterations,
        reporter=reporter,
        run_logger=run_logger,
        return_status=True,
        project_context=project_context,
        risk_context_block=risk_context_block,
    )
    # The real producer honors ``return_status=True`` and hands back
    # ``(findings, succeeded)``. A test double that patches the producer and
    # ignores the kwarg returns a bare list — read that as a completed call
    # (``succeeded=True``): a bare list represents "the producer returned",
    # which is exactly a success for cache-write purposes.
    if isinstance(result, tuple):
        findings, succeeded = result
    else:
        findings, succeeded = result, True
    if succeeded:
        purity_verdict = [
            r for r in findings if r.source == GRANULARITY_SPLIT_SOURCE
        ]
        detail_body = _read_step_detail_body(plan, plan_path, step, repo_root)
        impl_tests_text = _impl_tests_section_text(detail_body)
        cache.entries[step.id] = PurityCacheEntry(
            step_id=step.id,
            cache_key=combined_key,
            detail_hash=components.detail_hash,
            all_files_fingerprint=components.all_files_fingerprint,
            change_type=components.change_type,
            depends_on=list(components.depends_on),
            purity_verdict_logic_version=components.logic_version,
            detail_relpath=_step_detail_relpath(plan, plan_path, step, repo_root),
            findings=purity_verdict,
            impl_tests_text=impl_tests_text,
            checked_at=_utc_now_iso(),
            risk_context_rendered=bool(risk_context_block),
        )
        save_purity_cache(cache_path, cache)
    return _finish(
        _tag_purity_verdict_provenance(findings, "fresh"),
        succeeded,
    )


def _tag_purity_verdict_provenance(
    findings: Sequence["Recommendation"], provenance: str
) -> list["Recommendation"]:
    """Return transiently tagged copies of structural purity verdicts.

    Cache entries deliberately retain their unlabelled findings: provenance
    describes this retrieval, rather than the live call that originally wrote
    the cache baseline.
    """
    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

    return [
        replace(finding, purity_verdict_provenance=provenance)
        if finding.source == GRANULARITY_SPLIT_SOURCE
        else finding
        for finding in findings
    ]


def _read_step_detail_body(
    plan: Plan, plan_path: Path, step: Step, repo_root: Path
) -> str:
    """Read a step's detail-file text, or ``""`` when it has no detail file.

    Raises ``DetailFormatError`` uncaught when the body is present and
    readable but declares an unsupported or malformed format version.
    """
    if step.detail:
        detail_path = repo_root / step.detail
    else:
        detail_path = derive_detail_path(plan_path, plan, step)
    if not detail_path.is_file():
        return ""
    body = detail_path.read_text(encoding="utf-8")
    require_supported_detail_format_version(body, path=detail_path)
    return body


def _step_detail_relpath(
    plan: Plan, plan_path: Path, step: Step, repo_root: Path
) -> str:
    """The step's detail-file path relative to ``repo_root`` (posix)."""
    if step.detail:
        return step.detail
    derived = derive_detail_path(plan_path, plan, step)
    try:
        return derived.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return derived.as_posix()


def _format_already_implemented_block(
    plan: Plan, step: Step, repo_root: Path
) -> str:
    """Render ``heuristic_already_done`` hits scoped to ``step``.

    Renders as bullets naming the file, symbol, and pattern that fired.
    Empty result (no hits, heuristic skipped a done step, or the
    heuristic crashed for any reason) renders as a single-line note
    rather than an empty section — so the prompt template never shows
    a bare placeholder. Heuristic failures are swallowed: this is a
    best-effort signal, not a gate, and detail keeps working when review's
    primitives otherwise misbehave. A present unsupported detail remains a
    hard refusal rather than degrading this context.
    """
    try:
        hits = heuristic_already_done(plan, repo_root)
    except DetailFormatError:
        raise
    except Exception:
        return "_(heuristic skipped — could not scan plan files)_"
    step_hits = [h for h in hits if h.step_id == step.id]
    if not step_hits:
        return "_no already-implemented signal for this step_"
    lines: list[str] = [
        "The deterministic heuristic flagged the following file(s) as "
        "possibly already implementing parts of this step. Confirm with "
        "Read/Grep before relying on it:",
        "",
    ]
    for h in step_hits:
        lines.append(
            f"- `{h.file}` — symbol `{h.symbol}` matched pattern `{h.pattern}`"
        )
    return "\n".join(lines)


def extract_plan_references(plan_path: Path) -> str:
    """Lift the ``## References`` section body out of a plan's prose.

    Returns the trimmed section text when the plan has a populated
    References section, or an empty string when:

    - the plan file can't be read,
    - it has no frontmatter (parser would have rejected it earlier),
    - the body has no ``## References`` heading, OR
    - the section body is empty / only a TODO placeholder.

    Uses ``scope_fence.extract_h2_sections`` (fence-aware, case-insensitive
    via its lowercased keys) rather than a hand-rolled heading scanner — a
    fenced code block quoting a ``## References`` line no longer gets
    mistaken for a real section boundary.
    """
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        split = _split_frontmatter(text)
    except Exception:
        return ""
    body = split.body
    if not body:
        return ""
    section = extract_h2_sections(body, ignore_fenced_code=True).get(
        "references", ""
    ).strip()
    if not section:
        return ""
    if _is_placeholder_section(section):
        return ""
    return section


# Backtick-quoted token containing at least one ``/`` and ending in a
# recognized source/config/markdown extension, or in an exact extensionless
# name from ``_EXTENSIONLESS_FILENAMES`` below. Conservative on purpose
# — un-backticked path mentions in prose produce too many false
# positives. The extension list mirrors what the heuristic touches plus
# common docs extensions so a YAML config or buildspec citation lands.
_PATH_EXT_ALT = (
    "py|ts|tsx|js|jsx|mjs|cjs|go|rs|java|kt|rb|swift|"
    "md|txt|json|toml|yaml|yml|sh|sql|css|scss|html"
)

# Extensionless filenames recognized exactly (case-sensitive, no suffix such as
# ``Dockerfile.dev``). A fixed list, not a pattern, so an arbitrary backticked
# identifier never reads as a file.
_EXTENSIONLESS_FILENAMES = ("Dockerfile",)
_EXTENSIONLESS_ALT = "|".join(_EXTENSIONLESS_FILENAMES)

_PATH_MENTION_RE = re.compile(
    rf"`([^`\s]*?/[^`\s]*?\.(?:{_PATH_EXT_ALT})|[^`\s]*?/(?:{_EXTENSIONLESS_ALT}))`"
)

# Bare (directory-less) filename tokens — the companion to the path regex above.
_FILENAME_MENTION_RE = re.compile(
    rf"`([^`\s/]+?\.(?:{_PATH_EXT_ALT})|(?:{_EXTENSIONLESS_ALT}))`"
)


def extract_path_mentions(body: str) -> set[str]:
    """Pull backtick-quoted file path tokens from a markdown body.

    Returns a set of path strings (no leading/trailing slashes). The
    regex requires at least one slash and a known extension (or an exact
    ``_EXTENSIONLESS_FILENAMES`` name) so prose that backticks bare
    identifiers (no slash) doesn't match.

    Used by :func:`review.check_files_coherence` to compare the detail
    body's path mentions against the step's declared ``files:``.
    """
    if not body:
        return set()
    return {m.group(1) for m in _PATH_MENTION_RE.finditer(body)}


def extract_filename_mentions(body: str) -> set[str]:
    """Pull backtick-quoted *bare* filenames (no directory) from a body.

    Companion to :func:`extract_path_mentions`, which requires a slash so
    prose backticking a bare identifier can't match. That makes a repo-root
    file (``BACKLOG.md``, ``CLAUDE.md``) invisible to it no matter how often
    the body cites it. Callers asking "was this declared file discussed?"
    match these against a declared path's basename; the near-miss direction
    deliberately keeps using the path-shaped set. A bare token needs a known
    extension or an exact ``_EXTENSIONLESS_FILENAMES`` name. See BUG_BACKLOG.
    """
    if not body:
        return set()
    return {m.group(1) for m in _FILENAME_MENTION_RE.finditer(body)}


def parse_detail_file_sections(text: str) -> dict[str, str]:
    """Split a detail file body into ``{token: section_body}``.

    Tuned for the detail file's fixed seven-section required schema
    (Summary / Table of Contents / Why / Files / Implementation / Tests /
    Acceptance) while still preserving optional H2s such as Input,
    References, and Deferred. Token keys are the lowercased first
    significant word (matches ``_REQUIRED_H2_TOKENS`` for required sections)
    so callers can do ``sections.get("summary")``,
    ``sections.get("acceptance")``.

    Body for each section runs from the line *after* its heading up to
    (but not including) the next H2 / H1 / EOF. Whitespace is trimmed.

    Duplicates a primitive that lives in ``review.split_body_sections``
    deliberately — the detail-file schema is a *fixed* seven-section
    contract, not the more flexible plan-body outline. Sharing one
    parser would force the detail check toward the more permissive
    shape.

    Fence-aware: a fenced example containing a line that looks like a real
    heading (e.g. ``## Acceptance criteria`` shown as illustration inside
    ``## Implementation``) must not be read as — or split off — a section
    of its own.
    """
    sections: dict[str, str] = {}
    if not text:
        return sections

    higher_re = re.compile(r"^(#|##)\s+", re.MULTILINE)
    higher_matches = _matches_outside_fences(higher_re, text)

    for m in _matches_outside_fences(_H2_HEADING_RE, text):
        token = m.group(1).lower()
        # The H2 heading line ends at the line break; section body
        # starts on the next line.
        line_end = text.find("\n", m.end())
        if line_end == -1:
            sections[token] = ""
            continue
        section_start = line_end + 1
        next_match = next(
            (c for c in higher_matches if c.start() >= section_start), None
        )
        section_end = next_match.start() if next_match else len(text)
        sections[token] = text[section_start:section_end].strip("\n")
    return sections


def parse_acceptance_bullets(detail_body: str) -> list[str]:
    """Extract bullet text from a detail file's ``## Acceptance criteria``.

    Returns a list of bullet strings (leading ``-``/``*`` stripped,
    surrounding whitespace trimmed). Empty list when no acceptance
    section exists or it contains no bullet lines — the launcher uses
    that signal to fall back to the standard reconcile verdict for
    the step.

    Multi-line bullets aren't supported: the parser stops at the next
    bullet or the next H2 heading, whichever comes first. A bullet like
    ``- thing\n  with indented continuation`` keeps only the first line.
    Acceptable for the deep verifier — claude reads the first line as
    the criterion summary, and the full detail is in the rendered
    context anyway.
    """
    sections = parse_detail_file_sections(detail_body)
    section_body = sections.get("acceptance", "")
    if not section_body:
        return []

    bullets: list[str] = []
    bullet_re = re.compile(r"^\s*[-*]\s+(.+)$")
    for line in section_body.splitlines():
        m = bullet_re.match(line)
        if m:
            bullets.append(m.group(1).strip())
    return bullets


def _strip_whole_bare_fence_wrapper(lines: list[str]) -> list[str]:
    """Strip a bare first/last reply wrapper before nested fences are scanned."""
    if len(lines) < 2:
        return lines
    opening_match = _FENCE_OPEN_RE.match(lines[0].rstrip("\r\n"))
    closing_match = _FENCE_CLOSE_RE.match(lines[-1].rstrip("\r\n"))
    if (
        opening_match is None
        or closing_match is None
        or opening_match.end() != len(lines[0].rstrip())
        or _fenced_code_spans(lines[0]).unmatched_opening != 0
        or not _fence_run_closes(
            opening_match.group(1)[0],
            len(opening_match.group(1)),
            closing_match.group(1),
        )
    ):
        return lines
    return lines[1:-1]


def _strip_bare_fence_lines(lines: list[str]) -> list[str]:
    """Strip a leading and/or trailing bare fence line, independently. See
    DETAIL_FORMAT.md rule 2 for the full, non-obvious contract. All three
    current call sites pass already-``.strip()``ed text, so ``lines[0]``
    is not expected to be blank — but a blank ``lines[0]`` is defended
    against (falls through to the no-leading-fence case) rather than
    assumed impossible, since a prior version crashed on it.
    """
    if not lines:
        return lines
    text = "".join(lines)
    scan = _fenced_code_spans(text)
    opening_match = _FENCE_OPEN_RE.match(lines[0].rstrip("\r\n"))
    opens_with_fence = opening_match is not None and any(
        start == 0 for start, _end in scan.spans
    )
    if not opens_with_fence:
        if _FENCE_CLOSE_RE.match(lines[-1].rstrip("\r\n")):
            if scan.unmatched_opening is not None:
                # Strip only a lone, partner-less closer (rule 2).
                trailing_line_start = len(text) - len(lines[-1])
                if scan.unmatched_opening == trailing_line_start:
                    lines = lines[:-1]
        return lines
    opening_run = opening_match.group(1)
    lines = lines[1:]
    if lines:
        closing_match = _FENCE_CLOSE_RE.match(lines[-1].rstrip("\r\n"))
        trailing_line_start = len(text) - len(lines[-1])
        trailing_is_scanner_artifact = scan.unmatched_opening == trailing_line_start
        if (
            (
                trailing_is_scanner_artifact
                or any(start == 0 and end == len(text) for start, end in scan.spans)
            )
            and closing_match is not None
            and _fence_run_closes(opening_run[0], len(opening_run), closing_match.group(1))
        ):
            lines = lines[:-1]
    return lines


# Each marker must be alone on its own line — matched independently (not as
# one paired regex) so an ambiguous count (zero, or more than one, of either
# marker) is detected explicitly rather than resolved by picking whichever
# occurrence a single greedy match happens to pair first — and, like every
# other line-anchored marker this module matches (H2 headings, the deferrals
# envelope), only outside fenced code, so a fenced example illustrating the
# marker's own syntax can't stand in for a real occurrence. See
# DETAIL_FORMAT.md rule 3 for the full contract this implements.
_DETAIL_RESPONSE_START_LINE_RE = re.compile(
    r"^[ \t]*<!--\s*plan-tool:detail-response-start\s*-->[ \t]*\r?$",
    re.MULTILINE,
)
_DETAIL_RESPONSE_END_LINE_RE = re.compile(
    r"^[ \t]*<!--\s*plan-tool:detail-response-end\s*-->[ \t]*\r?$",
    re.MULTILINE,
)


def parse_detail_response(raw: str) -> Optional[str]:
    """Pull the markdown body out of a claude response.

    The common case is a plain response starting with ``#``. Full contract:
    DETAIL_FORMAT.md rules 1-4. Non-obvious invariant: the wrapper sentinel
    (rule 3.1) is checked *before* the plain path, unconditionally, whenever
    exactly one of each marker is present — not only when the plain path
    fails — since the wrapped content's own H1 is often already unfenced and
    would otherwise be found directly, silently ignoring the end marker and
    everything meant to be excluded after it.

    Returns ``None`` when the response is empty, has no parseable body at
    all, or is missing more than one required section.

    Section matching is case-insensitive and accepts trailing modifiers
    on the heading (``## Why we did this`` still satisfies ``## Why``).
    Order isn't enforced.
    """
    text = raw.strip()
    if not text:
        return None

    starts = _matches_outside_fences(_DETAIL_RESPONSE_START_LINE_RE, text)
    ends = _matches_outside_fences(_DETAIL_RESPONSE_END_LINE_RE, text)
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0].start() >= ends[0].start():
            return None
        inner = text[starts[0].end() : ends[0].start()].strip()
        if not inner:
            return None
        inner_lines = _strip_bare_fence_lines(
            _strip_whole_bare_fence_wrapper(inner.splitlines(keepends=True))
        )
        # The sentinel exists specifically so the model can add commentary
        # it can't avoid — including *inside* the brackets, before the
        # title — so the same preamble-skip the plain path gets applies
        # here too. If nothing unfenced is found (e.g. the bracketed
        # content is itself entirely fenced), trust the bracketed content
        # as-is rather than rejecting what the sentinel was built to accept.
        inner_first_heading = _detail_response_body_start(inner_lines)
        if inner_first_heading is not None:
            text = "".join(inner_lines[inner_first_heading:]).strip()
        else:
            text = "".join(inner_lines).strip()
    else:
        lines = _strip_bare_fence_lines(
            _strip_whole_bare_fence_wrapper(text.splitlines(keepends=True))
        )
        first_heading = _detail_response_body_start(lines)
        if first_heading is None:
            return None
        text = "".join(lines[first_heading:]).strip()
    if not text:
        return None

    # The accepted body must have a valid carrier H1 — the marker slot the
    # writer stamps at write time (``stamp_detail_format_version_marker``).
    # A response starting at ``## Summary`` (no H1) or an indented H1 has
    # nowhere to put the declaration, so it is rejected here rather than
    # silently reading as an absent (version 1) declaration later.
    if locate_detail_format_carrier(text) is None:
        return None

    headings = {
        m.group(1).lower()
        for m in _matches_outside_fences(_H2_HEADING_RE, text)
    }
    missing = [tok for tok in _REQUIRED_H2_TOKENS if tok not in headings]
    if len(missing) > 1:
        return None
    if len(missing) == 1:
        display = _REQUIRED_H2_DISPLAY[missing[0]]
        text = f"{text.rstrip()}\n\n## {display}\n\n{_STUB_SECTION_BODY}"
    return text


def stamp_detail_format_version_marker(body: str) -> str:
    """Stamp the current marker in the fixed post-H1 slot.

    Preserves text outside consecutive slot markers; see ``DETAIL_FORMAT.md``.
    """
    carrier = locate_detail_format_carrier(body)
    if carrier is None:
        raise DetailError(
            "stamp_detail_format_version_marker: body has no valid carrier "
            "H1 (a real, unindented H1 as the document's first non-blank "
            "line) to stamp a format-version marker after"
        )
    h1_idx, slot_idx = carrier
    lines = body.splitlines(keepends=True)

    # Drop every consecutive marker-shaped line at the slot (any payload —
    # collapses two stacked proposals to one current marker).
    idx = slot_idx
    while idx < len(lines) and _DETAIL_FORMAT_VERSION_MARKER_RE.match(lines[idx]):
        idx += 1
    # Skip blank lines to the real tail start, mirroring
    # ``locate_detail_format_carrier``'s own blank-skipping rule — otherwise
    # a second stamp would double the blank line left behind by dropping the
    # marker this function itself inserted, breaking idempotency.
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1

    head = lines[: h1_idx + 1]
    terminator = _line_terminator(head[-1]) or "\n"
    if not _line_terminator(head[-1]):
        head[-1] += terminator
    tail = lines[idx:]
    between = [terminator, f"{render_detail_format_version_marker()}{terminator}"]
    if tail:
        between.append(terminator)
    return "".join([*head, *between, *tail])


@dataclass(frozen=True)
class DetailDeferral:
    """A body-section bucket a detail step routes to ``## Deferred``.

    ``rationale`` is the model's short "what within the section, and why" note;
    it becomes the recorded flat node's rationale so a confirmed deferral
    renders as ``- {title} — {rationale}``. Empty when the envelope omits it.
    """

    concept_id: str
    step_id: int
    rationale: str = ""


@dataclass(frozen=True)
class ParsedDetailResponse:
    """The publishable Markdown body and its transport-only deferral links."""

    body: str
    deferrals: tuple[DetailDeferral, ...] = ()


def parse_structured_detail_response(
    raw: str,
    *,
    step: Optional[Step] = None,
    plan: Optional[Plan] = None,
    candidate_buckets: Optional[dict[str, str]] = None,
) -> Optional[ParsedDetailResponse]:
    """Split and validate the required detail deferral envelope.

    Shape validation is always strict.  Supplying ``step``, ``plan``, and
    ``candidate_buckets`` (the body-section deferral candidates, keyed by
    ``concept_id``) additionally validates that each deferral targets a known
    body-section bucket owned by (or unowned and free for) this step. The
    target resolves against the current plan body, not a persisted record, so
    a step can record a fresh pending decision on a record-absent plan.
    ``None`` for any of the three uses the same retry/failure path as an
    invalid Markdown body.
    """
    stripped = raw.strip()
    match = _find_real_deferrals_match(stripped)
    if match is None:
        return None
    body = parse_detail_response(stripped[: match.start()].rstrip())
    if body is None:
        return None
    try:
        payload = json.loads(match.group("payload"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {"deferrals"}:
        return None
    raw_deferrals = payload["deferrals"]
    if not isinstance(raw_deferrals, list):
        return None

    deferrals: list[DetailDeferral] = []
    seen: set[tuple[int, str]] = set()
    for raw_deferral in raw_deferrals:
        if (
            not isinstance(raw_deferral, dict)
            or not {"concept_id", "step_id"} <= set(raw_deferral)
            <= {"concept_id", "step_id", "rationale"}
            or not isinstance(raw_deferral["concept_id"], str)
            or not isinstance(raw_deferral["step_id"], int)
            or isinstance(raw_deferral["step_id"], bool)
            or not isinstance(raw_deferral.get("rationale", ""), str)
        ):
            return None
        deferral = DetailDeferral(
            concept_id=raw_deferral["concept_id"],
            step_id=raw_deferral["step_id"],
            rationale=" ".join(raw_deferral.get("rationale", "").split()),
        )
        identity = (deferral.step_id, deferral.concept_id)
        if identity in seen:
            return None
        seen.add(identity)
        deferrals.append(deferral)

    supplied = (step is not None, plan is not None, candidate_buckets is not None)
    if any(supplied) and not all(supplied):
        return None
    if all(supplied):
        assert step is not None and plan is not None and candidate_buckets is not None
        owners: dict[str, set[int]] = {}
        for candidate in plan.steps:
            for concept_id in candidate.concept_ids:
                owners.setdefault(concept_id, set()).add(candidate.id)
        for deferral in deferrals:
            concept_owners = owners.get(deferral.concept_id, set())
            if (
                deferral.step_id != step.id
                or deferral.concept_id not in candidate_buckets
                or (concept_owners and step.id not in concept_owners)
            ):
                return None
        deferred_section = parse_detail_file_sections(body).get("deferred", "")
        mentioned_ids = re.findall(
            r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])",
            deferred_section,
        )
        if set(mentioned_ids) != {
            deferral.concept_id for deferral in deferrals
        }:
            return None
    return ParsedDetailResponse(body=body, deferrals=tuple(deferrals))


# A marker line that opens one complete comment running to end-of-text: the
# only shape that is an envelope (however malformed its payload) rather than
# marker-like prose inside the body. A cut-off, unterminated envelope is
# deliberately not repaired: it gets a full regeneration.
_DETAIL_DEFERRALS_COMMENT_TAIL_RE = re.compile(
    r"<!--\s*" + _DETAIL_DEFERRALS_MARKER + r"\s*\n(?:(?!-->).)*-->",
    re.DOTALL,
)


def _body_for_deferrals_repair(raw: str) -> Optional[str]:
    """Keep a valid body when only its trailing envelope needs repair."""
    stripped = raw.strip()
    markers = _matches_outside_fences(_DETAIL_DEFERRALS_MARKER_START_RE, stripped)
    if not markers:
        return parse_detail_response(stripped)
    if _DETAIL_DEFERRALS_COMMENT_TAIL_RE.fullmatch(
        stripped, markers[-1].start()
    ) is None:
        return None  # Truncating here could drop body sections.
    match = _find_real_deferrals_match(stripped)
    if match is not None:
        try:
            json.loads(match.group("payload"))
        except (json.JSONDecodeError, TypeError):
            pass
        else:
            return None  # Valid JSON with a bad deferral contract needs a full reply.
    return parse_detail_response(stripped[: markers[-1].start()].rstrip())


def _strip_structural_findings_preserving_deferrals(raw: str) -> str:
    """Remove the prose-only purity block without consuming the envelope."""
    stripped = raw.strip()
    match = _find_real_deferrals_match(stripped)
    if match is None:
        return _STRUCTURAL_BLOCK_RE.sub("", raw)
    body = _STRUCTURAL_BLOCK_RE.sub("", stripped[: match.start()]).rstrip()
    return f"{body}\n\n{stripped[match.start():]}"


def update_step_detail_field(
    plan_path: Path,
    step_id: int,
    detail_rel_path: str,
) -> None:
    """Set ``step.detail`` on ``step_id`` to ``detail_rel_path`` and rewrite the plan.

    Round-trips through ``parse_plan`` → in-memory mutation →
    ``write_plan``, which preserves the prose body byte-for-byte and
    re-validates the schema. Only the targeted step's ``detail:`` field
    changes; every other step and plan-level field stays put.

    The caller is responsible for passing a path string in the form they
    want stored — typically repo-relative, since that's how every
    consumer (``run`` / ``review`` / ``jira``) reads it back. This helper
    doesn't normalize.

    Raises:
        DetailError: plan file fails to parse or validate; ``step_id``
            isn't in the plan; or the post-mutation plan fails schema
            re-validation. The original plan file is untouched on any
            failure.
    """
    try:
        plan = parse_plan(plan_path)
    except UnsupportedPlanFormatVersionError:
        raise
    except (ParseError, ValidationError) as exc:
        raise DetailError(f"failed to parse {plan_path}: {exc}") from exc
    try:
        step = plan.step_by_id(step_id)
    except KeyError as exc:
        raise DetailError(str(exc)) from exc
    step.detail = detail_rel_path
    try:
        write_plan(plan_path, plan)
    except ValidationError as exc:
        raise DetailError(
            f"plan would fail validation after mutation: {exc}"
        ) from exc


@dataclass(frozen=True)
class DetailResult:
    """One step's outcome from a single ``generate_detail`` run.

    For successful writes: ``written=True`` and ``output_path`` exists on
    disk. For dry-run: ``written=False`` and ``prompt`` carries the
    rendered template. For everything else (idempotent skip, claude
    failure, write failure): ``written=False`` and ``skipped_reason``
    explains why.
    """

    step_id: int
    output_path: Path
    written: bool
    skipped_reason: Optional[str] = None
    prompt: Optional[str] = None
    deferrals: tuple[DetailDeferral, ...] = ()


@dataclass(frozen=True)
class _RunGradeDetailDispatch:
    """Parsed run-grade input handed to setup."""

    plan: Plan
    jobs: int


@dataclass(frozen=True)
class _RunGradeDetailSetup:
    """Prepared run-grade state passed from setup into authoring."""

    plan: Plan
    compute_plan_fingerprint: Callable[[Path], str]
    plan_fingerprint: str
    concept_tree: Optional[ConceptTree]
    regeneration_step_ids: set[int]
    candidate_buckets: dict[str, str]
    require_deferral_envelope: bool
    target_steps: list[Step]
    reporter: ProgressReporter
    prompt_fn: Callable[[str], str]
    run_logger: Optional[RunLogWriter]
    plan_slug: str
    project_context: str
    cached_by_id: dict[int, Optional[Checkpoint]]
    invoke_total: int
    invoke_idx: int


def shell_detail_invoker(prompt: str) -> str:
    """Production invoker: run ``claude -p`` and capture stdout.

    Delegates to :func:`plan_tool.shell.claude_invoke`. Returns ``""``
    when the executable isn't on PATH; the orchestrator's per-step
    handler treats that as a parse failure and records a clean
    ``DetailResult`` skip.
    """
    _, stdout = claude_invoke(prompt)
    return stdout


def _scaled_detail_budget_for_step(step: Step, budget: IterativeBudget) -> IterativeBudget:
    """Return the per-step detail-quality budget after complexity scaling.

    Scaling applies only to the default cap. A non-default cap is treated as
    operator intent and left untouched; unset complexity keeps the full default
    depth. See docs/cli/detail.md (`--iterate` complexity scaling: low=1 /
    medium=2 / high|unknown=3).
    """
    if not budget.enabled or budget.max_iterations != DEFAULT_MAX_ITERATIONS:
        return budget
    caps = {
        Complexity.LOW: 1,
        Complexity.MEDIUM: 2,
        Complexity.HIGH: DEFAULT_MAX_ITERATIONS,
    }
    cap = caps.get(step.complexity, DEFAULT_MAX_ITERATIONS)
    if cap >= budget.max_iterations:
        return budget
    # replace() (not a field-by-field rebuild) so every other field —
    # hard_budget_seconds and op_started_at (#123) included — survives the
    # per-step cap scaling instead of silently resetting to its default.
    return replace(budget, max_iterations=cap)


@dataclass(frozen=True)
class _StepAuthoringOutcome:
    """One step's result from the concurrency-safe authoring worker.

    Carries everything the plan-mutating serial tail in ``generate_detail``
    reads back. ``update`` is the deferred ``(step_id, detail_rel)`` record
    the caller feeds to ``update_step_detail_field`` — the worker never
    writes the plan itself. On a parse or write failure ``succeeded`` is
    False, ``update`` is None, and ``result`` carries the failed
    ``DetailResult`` for the caller to append (with ``phase_outcome`` /
    ``phase_reason`` for the run-log ``phase_end``).
    """

    succeeded: bool
    invoke_idx: int
    handle: object
    result: Optional[DetailResult] = None
    update: Optional[tuple[int, str]] = None
    body: Optional[str] = None
    deferrals: tuple[DetailDeferral, ...] = ()
    purity_findings: "list[Recommendation]" = field(default_factory=list)
    elapsed: float = 0.0
    raw_bytes: int = 0
    phase_outcome: str = "success"
    phase_reason: str = ""


def _author_step_detail(
    step: Step,
    *,
    prompt: str,
    output_path: Path,
    cached: Optional[Checkpoint],
    input_hash: str,
    ckpt_path: Path,
    ckpt_name: str,
    plan_slug: str,
    phase_name: str,
    invoke_idx: int,
    invoke_total: int,
    reporter: ProgressReporter,
    run_logger: Optional[RunLogWriter],
    invoker: DetailInvoker,
    repo_root: Path,
    plan_path: Path,
    capture_scenarios: bool,
    arm: Optional[str],
    foundational_invoker: Optional[SweepInvoker],
    budget_blocks: Sequence[tuple[str, int]] = (),
    plan: Optional[Plan] = None,
    candidate_buckets: Optional[dict[str, str]] = None,
    require_deferral_envelope: bool = False,
) -> _StepAuthoringOutcome:
    """Turn one step into a written detail file — the concurrency-safe unit.

    Given an immutable snapshot (the pre-rendered ``prompt`` and the already
    resolved ``cached`` checkpoint), run the resume-or-invoke → parse →
    checkpoint → write sequence and return a ``_StepAuthoringOutcome``. Two
    invariants keep this dispatchable off-thread in step 2:

    - **No plan-file write.** The worker returns the deferred
      ``(step_id, detail_rel)`` record instead of calling
      ``update_step_detail_field``; the serial caller owns that mutation,
      the ``discard_checkpoint``, the convergence loop, and
      ``escalate_to_split``.
    - **No interactive stdin.** The resume/replace confirm is resolved by
      the caller before dispatch and its decision arrives as ``cached``.

    The ``save_checkpoint`` right after a successful parse stays here (the
    "claude succeeded but the file isn't durable yet" hedge); the matching
    ``discard_checkpoint`` runs in the caller only after the plan pointer is
    set. Behavior at the single-threaded path is byte-for-byte unchanged.

    """
    _reject_unmatched_plan_fence(plan_path)
    step_purity_findings: "list[Recommendation]" = []
    body: Optional[str]
    parsed_deferrals: tuple[DetailDeferral, ...]
    if cached is not None:
        raw = cached.payload
        if not require_deferral_envelope:
            parsed_cached = parse_structured_detail_response(raw)
            if parsed_cached is not None:
                body = (
                    parsed_cached.body if not parsed_cached.deferrals else None
                )
            elif f"<!-- {_DETAIL_DEFERRALS_MARKER}" in raw:
                body = None
            else:
                body = parse_detail_response(raw)
            parsed_deferrals = ()
        else:
            parsed_cached = parse_structured_detail_response(
                raw, step=step, plan=plan, candidate_buckets=candidate_buckets
            )
            body = parsed_cached.body if parsed_cached is not None else None
            parsed_deferrals = (
                parsed_cached.deferrals if parsed_cached is not None else ()
            )
        elapsed = 0.0
        handle = reporter.start_step(
            invoke_idx,  # not incremented — resumed, not invoked
            invoke_total,
            f"step {step.id}: {step.title} (resumed from checkpoint)",
        )
        if body is None:
            handle.fail(elapsed, "cached detail response no longer parses")
            try:
                discard_checkpoint(ckpt_path)
            except OSError as exc:
                tool(
                    f"failed to discard unparseable checkpoint {ckpt_path} "
                    f"({exc}); the next run may retry it"
                )
            else:
                if run_logger is not None:
                    run_logger.checkpoint_discard(
                        ckpt_name,
                        "parse_rejected",
                        step_id=step.id,
                        path=_repo_relative(ckpt_path, repo_root),
                    )
            return _StepAuthoringOutcome(
                succeeded=False,
                invoke_idx=invoke_idx,
                handle=handle,
                result=DetailResult(
                    step_id=step.id,
                    output_path=output_path,
                    written=False,
                    skipped_reason=(
                        "cached detail response no longer satisfies the "
                        "current parse contract"
                    ),
                ),
                elapsed=elapsed,
                phase_outcome="error",
                phase_reason="unparseable cached response",
            )
        # No claude call to time; close out the step immediately so the
        # heartbeat thread (StderrReporter) doesn't spin on nothing.
        handle.complete(elapsed, len(raw.encode("utf-8")))
    else:
        invoke_idx += 1
        # ``reporter.start_step`` wraps the whole retry loop, not one claude
        # call, so we deliberately do NOT pass a ``phase=`` kwarg here — the
        # run-log tee on the reporter would fire one ClaudeCallStart per
        # *step*, but the retry loop needs one per *attempt*. Per-attempt
        # events are emitted explicitly inside the loop below.
        handle = reporter.start_step(
            invoke_idx,
            invoke_total,
            f"step {step.id}: {step.title}",
        )
        start = time.monotonic()

        # Pre-send prompt-budget advisory — fires once per invoked step, right
        # before the retry loop (the retry's ``_REPROMPT_SUFFIX`` delta is
        # negligible). Skips resumed steps (the ``cached`` branch never reaches
        # here). Best-effort by contract; the ``except`` is belt-and-suspenders
        # so a slip never blocks the invoke, the write, or the return.
        # ``active_context_window()`` → the selected model's window where known,
        # else the leaf's default window.
        # Gates the backstop on the retry loop below: a swallowed failure here
        # leaves ``budget_covered`` False so the generic backstop stays a
        # fallback net rather than leaving the send with zero coverage.
        def _measure_prompt_budget(
            text: str, blocks: Sequence[tuple[str, int]]
        ) -> bool:
            """Advise and record; ``True`` when the measurement completed."""
            try:
                total_bytes = len(text.encode("utf-8"))
                budget = maybe_warn_prompt_budget(
                    total_bytes,
                    context_window=active_context_window(),
                    blocks=blocks,
                    surface=_DETAIL_BUDGET_SURFACE,
                    remedies=_DETAIL_BUDGET_REMEDIES,
                )
                record_prompt_budget(
                    repo_root,
                    plan_slug=plan_slug,
                    phase="detail",
                    total_bytes=total_bytes,
                    advisory=budget.level,
                    estimated_tokens=budget.estimated_tokens,
                    context_window=budget.context_window,
                    headroom_ratio=budget.headroom_ratio,
                    blocks=budget.blocks,
                )
                return True
            except Exception:
                return False

        budget_covered = _measure_prompt_budget(prompt, budget_blocks)

        # One retry on parse failure with a clarifying suffix. Most parse
        # failures are model-variance (preamble before `#`, dropped section,
        # stray fence) rather than structural — re-prompting with the exact
        # contract recovers them. Hard failures still surface after attempt 2
        # with the original "unparseable response" reason.
        raw = ""
        body = None
        parsed_deferrals = ()
        retry_suffix = _REPROMPT_SUFFIX
        repair_body: Optional[str] = None
        rejected_raw = ""
        repair_purity_findings: "list[Recommendation]" = []
        for attempt in range(1, _MAX_INVOKE_ATTEMPTS + 1):
            attempt_prompt = (
                prompt if attempt == 1 else prompt + retry_suffix
            )
            attempt_budget_covered = budget_covered
            if attempt > 1 and repair_body is not None:
                attempt_prompt = (
                    prompt
                    + "\n\n## Repair\n\nYour previous response was REJECTED: "
                    "the detail file parses, but its required deferrals "
                    "envelope is missing or has invalid JSON.\n\n"
                    "Previous response:\n\n"
                    + rejected_raw
                    + "\n\nReturn ONLY the trailing "
                    "`<!-- plan-tool-detail-deferrals` JSON envelope. "
                    "State the deferrals explicitly, using "
                    "`{\"deferrals\":[]}` when there are none. "
                    "Do not repeat the Markdown file.\n"
                )
                attempt_budget_covered = _measure_prompt_budget(
                    attempt_prompt,
                    (
                        *budget_blocks,
                        ("rejected-response", len(rejected_raw.encode("utf-8"))),
                    ),
                )
            if run_logger is not None:
                run_logger.claude_call_start(
                    phase=phase_name,
                    attempt=attempt,
                    prompt_bytes=len(attempt_prompt.encode("utf-8")),
                    prompt_sha256=hash_prompt(attempt_prompt),
                    step_id=step.id,
                )
                sink_ctx = run_logger.bind_shell_sink(
                    phase=phase_name, attempt=attempt,
                )
            else:
                sink_ctx = contextlib.nullcontext()
            with suppress_prompt_budget_backstop(
                active=attempt_budget_covered
            ), sink_ctx:
                raw = invoker(attempt_prompt)
            repair_match = (
                _find_real_deferrals_match(raw.strip())
                if repair_body is not None else None
            )
            repair_reply_valid = (
                repair_body is None
                or (repair_match is not None and repair_match.start() == 0)
            )
            parsed_raw = (
                f"{repair_body.rstrip()}\n\n{raw.strip()}"
                if repair_body is not None else raw
            )
            purity_candidate: "list[Recommendation]" = []
            # Defensive purity strip. The authoring prompt no longer asks
            # for the ``## Structural findings`` self-check — the
            # ``detail-quality`` pass owns mixed-step detection now — but a
            # model may still volunteer the block, so strip it BEFORE
            # parsing the body (it must never land in the written file) and
            # surface any MIXED-STEP it carries. Captured only on the
            # attempt that parses (so it matches the body actually written).
            purity_candidate = (
                repair_purity_findings if repair_body is not None
                else parse_mixed_step_findings(raw, step, plan_slug)
            )
            parsed_raw = _strip_structural_findings_preserving_deferrals(
                parsed_raw
            )
            if not require_deferral_envelope:
                parsed = parse_structured_detail_response(parsed_raw)
                if parsed is not None:
                    body = parsed.body if not parsed.deferrals else None
                elif f"<!-- {_DETAIL_DEFERRALS_MARKER}" in parsed_raw:
                    body = None
                else:
                    body = parse_detail_response(parsed_raw)
                parsed_deferrals = ()
            else:
                parsed = (
                    parse_structured_detail_response(
                        parsed_raw, step=step, plan=plan,
                        candidate_buckets=candidate_buckets,
                    ) if repair_reply_valid else None
                )
                body = parsed.body if parsed is not None else None
                parsed_deferrals = (
                    parsed.deferrals if parsed is not None else ()
                )
            if body is not None:
                step_purity_findings = purity_candidate
                raw = parsed_raw
                break
            if (
                attempt == 1 and require_deferral_envelope
            ):
                repair_body = _body_for_deferrals_repair(parsed_raw)
                if repair_body is not None:
                    rejected_raw = raw
                    repair_purity_findings = purity_candidate
            # Log the rejected raw response before retry so a later debugging
            # pass can tell whether the failure was a case the parser's
            # leniency should cover or genuinely unfixable.
            log_path = _log_parse_failure(
                repo_root=repo_root,
                plan_path=plan_path,
                step_id=step.id,
                attempt=attempt,
                raw_response=raw,
            )
            if run_logger is not None:
                # Reference the on-disk dump rather than embedding the raw
                # response (a typical claude response is well above the
                # 4096-byte per-line cap; ``parse-failures/`` is the durable
                # archive). ``raw_bytes`` is captured so callers can size the
                # failure even if logging itself failed (``log_path is None``).
                if log_path is None:
                    rel_failure_path = ""
                else:
                    try:
                        rel_failure_path = (
                            log_path.resolve()
                            .relative_to(repo_root.resolve())
                            .as_posix()
                        )
                    except ValueError:
                        rel_failure_path = str(log_path)
                run_logger.parse_failure(
                    phase=phase_name,
                    attempt=attempt,
                    failure_path=rel_failure_path,
                    step_id=step.id,
                    raw_bytes=len(raw.encode("utf-8")),
                )
            if attempt < _MAX_INVOKE_ATTEMPTS:
                suffix = f"; logged to {log_path}" if log_path else ""
                handle.notice(
                    f"step {step.id}: response failed parse "
                    f"(attempt {attempt}/{_MAX_INVOKE_ATTEMPTS}); "
                    + (
                        "retrying with envelope-only repair"
                        if repair_body is not None
                        else "retrying with template-conformance reminder"
                    )
                    + f"{suffix}",
                    kind="retry",
                )
        elapsed = time.monotonic() - start
        if body is None:
            handle.fail(elapsed, "claude returned an unparseable response")
            # Capture the FAILURE scenario — a re-runnable, discriminating
            # A/B case (this arm failed to parse this step).
            if capture_scenarios:
                capture_scenario(
                    "detail",
                    experiment=PROMPT_MODE_EXPERIMENT.name,
                    arm=arm_from_split(
                        arm, split=foundational_invoker is not None
                    ),
                    categories=[CATEGORY_FAILURE],
                    inputs={
                        "plan": _repo_relative(plan_path, repo_root),
                        "step_id": step.id,
                        "plan_sha": content_sha(plan_path),
                    },
                    outcome={
                        "status": "failed",
                        "reason": "unparseable response",
                    },
                    repo_root=repo_root,
                    run_id=getattr(run_logger, "run_id", None),
                )
            return _StepAuthoringOutcome(
                succeeded=False,
                invoke_idx=invoke_idx,
                handle=handle,
                result=DetailResult(
                    step_id=step.id,
                    output_path=output_path,
                    written=False,
                    skipped_reason=(
                        (
                            "claude returned an unparseable response "
                            "(missing required H2 sections, or no `#` "
                            "heading) "
                        )
                        + f"after {_MAX_INVOKE_ATTEMPTS} attempt(s)"
                    ),
                ),
                elapsed=elapsed,
                phase_outcome="error",
                phase_reason="unparseable response",
            )

        # Save checkpoint immediately after a successful parse, before the
        # missing-files warning, the write, and the plan-update — any of which
        # can throw and is the scenario this whole step exists to recover from.
        # Best-effort: a permissions / disk issue on ``.plan-tool/checkpoints/``
        # shouldn't abort a multi-step run that would otherwise succeed.
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw if require_deferral_envelope else body,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save checkpoint {ckpt_path} "
                f"({exc}); resume on next run will not be available "
                f"for step {step.id}"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    ckpt_name,
                    input_hash,
                    len(body.encode("utf-8")),
                    step_id=step.id,
                    path=_repo_relative(ckpt_path, repo_root),
                )

    # Soft-warn when fewer than half of the step's declared files are mentioned
    # in the body. Likely-drift signal — claude may have responded against a
    # different set of files than the step declares. Doesn't refuse: a
    # thoughtful detail file may legitimately discuss a subset.
    if step.all_files:
        declared = step.all_files
        mentioned = sum(1 for f in declared if f in body)
        if mentioned * 2 < len(declared):
            missing = [f for f in declared if f not in body]
            warn(
                f"step {step.id} detail body mentions "
                f"{mentioned} of {len(declared)} declared files; "
                f"missing: {', '.join(missing)}"
            )

    # Stamp before the write, not inside the try below: this is a pure string
    # operation on ``body`` (no I/O to fail), so running it first means a
    # stamp failure can never leave a prior file archived with nothing written
    # in its place. Every write carries the current marker.
    body = stamp_detail_format_version_marker(body)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # If a prior detail file lives at the canonical path (force overwrite,
        # user-accepted replace, or resume write after a partial earlier run),
        # move it into ``archive/`` first so the prior content survives.
        archived_prior = _archive_existing_detail(output_path)
        if archived_prior is not None:
            tool(f"archived previous detail to {archived_prior}")
        output_path.write_text(body + "\n", encoding="utf-8")
    except OSError as exc:
        handle.fail(elapsed, f"write failed: {exc}")
        return _StepAuthoringOutcome(
            succeeded=False,
            invoke_idx=invoke_idx,
            handle=handle,
            result=DetailResult(
                step_id=step.id,
                output_path=output_path,
                written=False,
                skipped_reason=f"write failed: {exc}",
            ),
            elapsed=elapsed,
            phase_outcome="error",
            phase_reason=f"write failed: {exc}",
        )

    # Detail file is on disk. Return the deferred plan-update record; the caller
    # (which owns plan mutation) calls ``update_step_detail_field`` and then
    # ``discard_checkpoint`` so the durability hedge survives until the pointer
    # is set. ``_archive_orphan_details`` runs in the caller for the same reason.
    detail_rel = _repo_relative(output_path, repo_root)
    return _StepAuthoringOutcome(
        succeeded=True,
        invoke_idx=invoke_idx,
        handle=handle,
        update=(step.id, detail_rel),
        body=body,
        deferrals=parsed_deferrals,
        purity_findings=step_purity_findings,
        elapsed=elapsed,
        raw_bytes=len(raw.encode("utf-8")),
    )


@dataclass(frozen=True)
class _DispatchItem:
    """One step resolved for concurrent authoring, everything the pool needs.

    Built by the serial pre-dispatch pass in :func:`_generate_detail_concurrent`
    (interactive replace/resume confirms and the sibling snapshot are all
    resolved before the pool starts) and consumed by the worker thread plus the
    serial tail. ``cached is not None`` marks a resume (no claude call);
    ``phase_cached`` mirrors it for the run-log ``phase_end``.
    """

    step: Step
    output_path: Path
    prompt: str
    cached: Optional[Checkpoint]
    input_hash: str
    ckpt_path: Path
    ckpt_name: str
    phase_cached: bool
    # Per-block prompt-budget breakdown, computed at the serial pre-dispatch
    # render; the worker can't rebuild it (it never sees plan/siblings), so the
    # frozen carrier delivers it for the invoke-time advisory.
    budget_blocks: tuple[tuple[str, int], ...] = ()


def _generate_detail_concurrent(
    *,
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    target_steps: list[Step],
    cached_by_id: dict[int, Optional[Checkpoint]],
    plan_slug: str,
    jobs: int,
    force: bool,
    reporter: ProgressReporter,
    run_logger: Optional[RunLogWriter],
    invoker: DetailInvoker,
    prompt_fn: Callable[[str], str],
    capture_scenarios: bool,
    arm: Optional[str],
    foundational_invoker: Optional[SweepInvoker],
    extract_lessons: bool,
    lessons_invoker: Optional[LessonsInvoker],
    strict_check: bool,
    equivalence_invoker: Optional[EquivalenceInvoker],
    prior_body: str,
    concept_tree: Optional[ConceptTree] = None,
    candidate_buckets: Optional[dict[str, str]] = None,
    require_deferral_envelope: bool = False,
    project_context: str = "",
) -> "tuple[list[DetailResult], list[tuple[int, Recommendation]]]":
    """Author ``target_steps`` with the per-step ``claude`` calls overlapping.

    The concurrency contract (see the ``generate_detail`` docstring and the
    step-2 plan):

    - **Pre-dispatch (serial, step order).** Resolve every interactive confirm
      (``_confirm_replace`` / ``_confirm_resume``) and compute **one** sibling
      snapshot *before* the pool starts, so no worker reads a half-written
      ``NN-*.md`` and authored content is schedule-independent. Render each
      prompt here too.
    - **Dispatch (concurrent).** Hand :func:`_author_step_detail` — render's
      already done, so really invoke → parse → checkpoint → write — to a
      ``ThreadPoolExecutor`` sized ``min(jobs, invoke_count)`` (never more
      threads than fresh invokes). Threads, not processes: the ``claude``
      shell-out is IO-bound and releases the GIL, and the shared invoker /
      reporter / run-logger are in-process objects.
    - **Serial tail (step order).** Everything that mutates the plan or crosses
      steps — ``update_step_detail_field``, ``discard_checkpoint``, the
      mixed-step heads-up, orphan archiving, scenario capture, lesson
      extraction, and the run-log ``phase_start`` / ``phase_end`` pairing —
      runs after the workers join, ordered by step id, so a ``jobs > 1`` run
      returns the same ``DetailResult`` sequence a serial run would.

    Failure isolation matches the serial loop's taxonomy exactly: only an
    unparseable ``None`` body or a write ``OSError`` yields a not-written
    ``DetailResult`` for one step while the others complete; **any other**
    exception out of the worker is a plan-level abort — collected across the
    pool and re-raised in step order after the join, never downgraded to a
    per-step skip.

    Returns ``(results, mixed_steps)`` for the caller to fold into its own
    lists (``mixed_steps`` feeds Phase B's recommend-only split pass). The
    ``--iterate`` / ``--split`` arms are refused by ``generate_detail`` before
    this runs, so there is no convergence loop and no in-loop split here.
    """
    results: list[DetailResult] = []
    mixed_steps: "list[tuple[int, Recommendation]]" = []

    # One pre-dispatch sibling snapshot: the ``.md`` files present in the
    # detail directory before any worker writes. All target steps share the
    # same ``plan-details/<slug>/`` directory, so a single listing (minus each
    # worker's own output path) reproduces ``_discover_siblings`` semantics
    # without letting thread schedule decide which siblings a worker sees.
    snapshot_dir = derive_detail_path(plan_path, plan, target_steps[0]).parent
    sibling_snapshot = (
        sorted(snapshot_dir.glob("*.md")) if snapshot_dir.is_dir() else []
    )

    # --- Pre-dispatch pass (serial, step order) ---------------------------
    dispatch: list[_DispatchItem] = []
    # Unlike the serial lifecycle's per-iteration render (which must reread
    # the plan after an in-loop accepted apply), ``plan`` never changes
    # across this single pre-dispatch pass — no convergence loop, no in-loop
    # split (see the class docstring) — so this is safe to compute once.
    risk_context_block = render_declared_risk_context(plan)
    for step in target_steps:
        output_path = derive_detail_path(plan_path, plan, step)

        # Already-exists replace confirm — resolved serially so no worker
        # thread ever reads a TTY. Non-TTY auto-declines (idempotent skip).
        if (
            not force
            and step.detail is not None
            and output_path.exists()
        ):
            if not _confirm_replace(
                prompt_fn,
                step_id=step.id,
                step_title=step.title,
                output_path=output_path,
            ):
                results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=False,
                        skipped_reason=(
                            "already exists (user declined replace; pass "
                            "--force to skip the prompt and overwrite)"
                        ),
                    )
                )
                continue

        siblings = [
            p for p in sibling_snapshot
            if p.resolve() != output_path.resolve()
        ]
        # Render once per step before the optional sweep: this fence grounds
        # its classification and the authoring prompt with identical context.
        scope_fence_block = render_scope_fence(
            plan_path,
            plan_intent=plan.intent or "",
            step_intent=step.intent or "",
        )
        foundational_block = ""
        if foundational_invoker is not None:
            # Serial by design: the sweep is a claude call, but it's an
            # experimental off-by-default path and its result must be baked
            # into the prompt before dispatch.
            try:
                sweep = run_foundational_logic_sweep(
                    _render_step_sweep_context(step, scope_fence_block),
                    foundational_invoker,
                    run_logger=run_logger,
                    step_id=step.id,
                )
                foundational_block = format_foundational_logic_block(sweep)
            except Exception as exc:  # noqa: BLE001 — never sink detail on a slip
                tool(f"foundational-logic sweep failed ({exc}); skipping")
        plan_references_block = extract_plan_references(plan_path)
        # Budget breakdown collected during the render below (no second
        # formatter pass) and stashed as a tuple on the carrier so the
        # off-thread worker warns too — it can't rebuild the blocks, it only
        # sees the ``_DispatchItem``.
        budget_blocks_collected: list[tuple[str, int]] = []
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=repo_root,
            sibling_details=siblings,
            plan_references_block=plan_references_block,
            scope_fence_block=scope_fence_block,
            risk_context_block=risk_context_block,
            foundational_logic_block=foundational_block,
            split_mode=foundational_invoker is not None,
            prior_body=prior_body,
            output_path=output_path,
            collect_blocks=budget_blocks_collected,
            concept_tree=concept_tree,
            candidate_buckets=candidate_buckets,
            project_context=project_context,
        )
        budget_blocks = tuple(budget_blocks_collected)

        input_hash = _detail_step_input_hash(
            plan_path, step, project_context=project_context
        )
        ckpt_path = checkpoint_path(
            repo_root, plan_slug, _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
        )
        ckpt_name = _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
        cached = cached_by_id[step.id]
        # Resume confirm — also serial (worker reads no stdin). A decline drops
        # the cached body so this step falls through to a fresh invoke.
        if cached is not None:
            try:
                created_at = datetime.fromisoformat(cached.created_at)
                age_seconds = (
                    datetime.now(timezone.utc) - created_at
                ).total_seconds()
            except ValueError:
                age_seconds = 0.0
            if not _confirm_resume(
                prompt_fn,
                step_id=step.id,
                step_title=step.title,
                checkpoint_age_seconds=age_seconds,
            ):
                declined_path = _repo_relative(ckpt_path, repo_root)
                try:
                    discard_checkpoint(ckpt_path)
                except OSError as exc:
                    tool(
                        f"failed to discard declined checkpoint {ckpt_path} "
                        f"({exc}); next run may re-prompt against the same "
                        "stale body"
                    )
                else:
                    if run_logger is not None:
                        run_logger.checkpoint_discard(
                            ckpt_name,
                            "user_declined_resume",
                            step_id=step.id,
                            path=declined_path,
                        )
                cached = None
        dispatch.append(
            _DispatchItem(
                step=step,
                output_path=output_path,
                prompt=prompt,
                cached=cached,
                input_hash=input_hash,
                ckpt_path=ckpt_path,
                ckpt_name=ckpt_name,
                phase_cached=cached is not None,
                budget_blocks=budget_blocks,
            )
        )

    # Worker count: never more threads than fresh invokes. A declined resume
    # became a fresh invoke, so recount here rather than reuse ``invoke_count``.
    invoke_items = [d for d in dispatch if d.cached is None]
    invoke_total = len(invoke_items)
    resolved_workers = min(jobs, max(1, invoke_total))
    # Stable display index per fresh invoke (1-based) for the reporter's
    # ``[N/M]`` counter. Under concurrency these interleave on stderr by
    # design (accepted); the durable result rows stay ordered.
    idx_by_id = {d.step.id: i for i, d in enumerate(invoke_items, start=1)}

    dispatch_by_id = {d.step.id: d for d in dispatch}

    def _run_worker(d: _DispatchItem) -> _StepAuthoringOutcome:
        invoke_idx = (idx_by_id[d.step.id] - 1) if d.cached is None else 0
        return _author_step_detail(
            d.step,
            prompt=d.prompt,
            output_path=d.output_path,
            cached=d.cached,
            input_hash=d.input_hash,
            ckpt_path=d.ckpt_path,
            ckpt_name=d.ckpt_name,
            plan_slug=plan_slug,
            phase_name=f"detail-step-{d.step.id:02d}",
            invoke_idx=invoke_idx,
            invoke_total=invoke_total,
            reporter=reporter,
            run_logger=run_logger,
            invoker=invoker,
            repo_root=repo_root,
            plan_path=plan_path,
            capture_scenarios=capture_scenarios,
            arm=arm,
            foundational_invoker=foundational_invoker,
            budget_blocks=d.budget_blocks,
            plan=plan,
            candidate_buckets=candidate_buckets,
            require_deferral_envelope=require_deferral_envelope,
        )

    # --- Dispatch (concurrent) -------------------------------------------
    outcomes_by_id: dict[int, _StepAuthoringOutcome] = {}
    errors_by_id: dict[int, BaseException] = {}
    with ThreadPoolExecutor(max_workers=resolved_workers) as pool:
        future_to_id = {
            pool.submit(_run_worker, d): d.step.id for d in dispatch
        }
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            exc = future.exception()
            if exc is not None:
                errors_by_id[sid] = exc
            else:
                outcomes_by_id[sid] = future.result()

    # A per-step parse/write failure comes back as a not-written
    # ``_StepAuthoringOutcome`` (isolated). Any real exception is a plan-level
    # abort: re-raise the first in step order, deterministically, after join.
    for step in target_steps:
        if step.id in errors_by_id:
            raise errors_by_id[step.id]

    # --- Serial tail (step order) ----------------------------------------
    for step in target_steps:
        if step.id not in outcomes_by_id:
            continue  # declined-replace skip — already recorded above
        outcome = outcomes_by_id[step.id]
        d = dispatch_by_id[step.id]
        phase_name = f"detail-step-{step.id:02d}"
        phase_outcome = "success"
        phase_reason = ""
        if run_logger is not None:
            run_logger.phase_start(
                phase_name, step_id=step.id, step_title=step.title
            )
        try:
            if not outcome.succeeded:
                # Worker already called ``handle.fail`` and built the skip.
                results.append(outcome.result)
                phase_outcome = outcome.phase_outcome
                phase_reason = outcome.phase_reason
                continue

            _, detail_rel = outcome.update
            try:
                update_step_detail_field(plan_path, step.id, detail_rel)
            except DetailError as exc:
                outcome.handle.fail(
                    outcome.elapsed, f"plan frontmatter update failed: {exc}"
                )
                results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=d.output_path,
                        written=False,
                        skipped_reason=(
                            f"plan frontmatter update failed: {exc} "
                            f"(file written at {d.output_path}; manual cleanup "
                            "needed — delete it or add the `detail:` pointer "
                            "to the step manually)"
                        ),
                    )
                )
                phase_outcome = "error"
                phase_reason = f"frontmatter update failed: {exc}"
                continue

            step.detail = detail_rel

            for pf in outcome.purity_findings:
                tool(f"mixed-step detected — {pf.body}", level="warning")
                mixed_steps.append((step.id, pf))

            try:
                discard_checkpoint(d.ckpt_path)
            except OSError as exc:
                tool(
                    f"failed to discard checkpoint {d.ckpt_path} "
                    f"({exc}); next run may waste a hash-match read"
                )
            else:
                if run_logger is not None:
                    run_logger.checkpoint_discard(
                        d.ckpt_name,
                        "durable_write",
                        step_id=step.id,
                        path=_repo_relative(d.ckpt_path, repo_root),
                    )

            for dest in _archive_orphan_details(d.output_path, step.id):
                tool(f"archived orphan detail to {dest}")

            # Close the reporter step (the fresh-invoke worker leaves this to
            # the caller, exactly as the serial loop does; the resume path
            # already completed its handle in the worker).
            outcome.handle.complete(outcome.elapsed, outcome.raw_bytes)

            if capture_scenarios and not d.phase_cached:
                capture_scenario(
                    "detail",
                    experiment=PROMPT_MODE_EXPERIMENT.name,
                    arm=arm_from_split(
                        arm, split=foundational_invoker is not None
                    ),
                    categories=categorize_scenario(
                        _detail_scenario_signals(step, plan)
                    ),
                    inputs={
                        "plan": _repo_relative(plan_path, repo_root),
                        "step_id": step.id,
                        "plan_sha": content_sha(plan_path),
                    },
                    outcome={"written": True, "step_title": step.title},
                    repo_root=repo_root,
                    run_id=getattr(run_logger, "run_id", None),
                )

            # Lesson capture is refused for jobs>1 at entry (needs --iterate);
            # no distill call here.

            results.append(
                DetailResult(
                    step_id=step.id,
                    output_path=d.output_path,
                    written=True,
                    deferrals=outcome.deferrals,
                )
            )
            # NB: no per-step commit here. The concurrent path's workers all
            # write their detail files *before* this serial tail runs, so a
            # ``git add -A`` here would sweep every sibling's file into the
            # first step's commit (no per-step isolation), and committing only
            # after the join gives no interruption-durability benefit anyway
            # (the expensive authoring already finished). The concurrent path
            # gets one batch commit at end-of-run instead (#122 is serial-only).
        finally:
            if run_logger is not None:
                extra: dict[str, object] = {
                    "step_id": step.id,
                    "cached": d.phase_cached,
                }
                if phase_reason:
                    extra["reason"] = phase_reason
                run_logger.phase_end(
                    phase_name,
                    # ``elapsed`` is the worker's measured claude-call time —
                    # a meaningful per-step duration even though the phase
                    # pair is emitted here in the serial tail.
                    duration_ms=int(outcome.elapsed * 1000),
                    outcome=phase_outcome,
                    **extra,
                )

    return results, mixed_steps


def _parse_detail_plan_and_dispatch(
    plan_path: Path,
    *,
    repo_root: Path,
    step_id: Optional[int],
    force: bool,
    dry_run: bool,
    invoker: DetailInvoker,
    reporter: Optional[ProgressReporter],
    extract_lessons: bool,
    resume: bool,
    prompt_fn: Optional[Callable[[str], str]],
    run_logger: Optional[RunLogWriter],
    budget: IterativeBudget,
    allow_split: bool,
    jobs: int,
    commit_step: Optional[Callable[[int, str], None]],
) -> _RunGradeDetailDispatch:
    """Validate run-grade modes and hand parsed input to setup."""
    # Defensive floor: the CLI rejects ``< 1``; anything slipping through runs
    # serially rather than raising or auto-resolving a worker count.
    if jobs < 1:
        jobs = 1
    # Guard the two plan-structure-mutating arms before run-grade setup so a
    # rejected combination leaves the plan untouched. Both are refused at the
    # function regardless of entry point — a direct caller is backstopped here,
    # not only at the CLI.
    if jobs > 1 and budget.enabled:
        raise DetailError(
            "jobs > 1 (concurrent detail authoring) is mutually exclusive "
            "with --iterate: the convergence loop re-reads and restructures "
            "the plan between iterations, which needs serial, ordered "
            "execution. Run the concurrent authoring pass, then --iterate "
            "serially."
        )
    if jobs > 1 and allow_split:
        raise DetailError(
            "jobs > 1 (concurrent detail authoring) is mutually exclusive "
            "with --split: an auto-split renumbers plan step ids, which "
            "workers holding step snapshots cannot tolerate. Author "
            "concurrently first, then --split in a serial follow-up."
        )
    if jobs > 1 and extract_lessons:
        raise DetailError(
            "jobs > 1 (concurrent detail authoring) is mutually exclusive "
            "with --lessons: lesson capture requires a clean detail-quality "
            "converge under --iterate, which needs serial execution."
        )

    try:
        plan = parse_plan(plan_path)
    except UnsupportedPlanFormatVersionError:
        raise
    except (ParseError, ValidationError) as exc:
        raise DetailError(f"failed to parse {plan_path}: {exc}") from exc

    return _RunGradeDetailDispatch(plan=plan, jobs=jobs)


def _prepare_run_grade_detail(
    plan_path: Path,
    plan: Plan,
    *,
    repo_root: Path,
    step_id: Optional[int],
    force: bool,
    dry_run: bool,
    reporter: Optional[ProgressReporter],
    resume: bool,
    prompt_fn: Optional[Callable[[str], str]],
    run_logger: Optional[RunLogWriter],
) -> _RunGradeDetailSetup:
    """Prepare run-grade state in prerequisite order before authoring."""
    project_context = project_profile_context(repo_root)
    # The concept record is optional for legacy plans. When present, load it
    # against the exact durable plan/detail fingerprint before authoring; a
    # stale record is never silently treated as absent.
    from plan_tool.review_persistence import compute_plan_fingerprint
    try:
        plan_fingerprint = compute_plan_fingerprint(plan_path)
    except Exception:
        # The fingerprint is provenance-only for decision records and telemetry.
        # A transient read failure must not discard already-written detail.
        plan_fingerprint = ""
    try:
        concept_tree = load_concepts(plan_path, plan_fingerprint)
    except (InvalidConceptTreeError, StaleConceptTreeError) as exc:
        raise DetailError(f"cannot use concept record: {exc}") from exc
    regeneration_step_ids = _included_deferral_step_ids(concept_tree, plan)

    # The buckets a detail step may defer are the plan's current body sections,
    # derived once here (record-independent) and threaded to the prompt, the
    # parse gate, and the persist tail so all three resolve an id identically.
    try:
        candidate_buckets = derive_candidate_buckets(
            plan, plan_path.read_text(encoding="utf-8")
        )
    except DetailError as exc:
        raise DetailError(f"{plan_path}: {exc}") from exc
    # Require (and validate) the deferral envelope whenever a deferral could be
    # recorded — any body-section bucket exists — or a concept record is on disk
    # (legacy full-tree discipline). A bare plan with neither keeps the lenient
    # shape-only parse it had before.
    require_deferral_envelope = bool(candidate_buckets) or concept_tree is not None

    if step_id is not None:
        try:
            target_steps: list[Step] = [plan.step_by_id(step_id)]
        except KeyError as exc:
            raise DetailError(str(exc)) from exc
    else:
        target_steps = list(plan.steps)
    if regeneration_step_ids:
        selected = {step.id for step in target_steps}
        target_steps.extend(
            step
            for step in plan.steps
            if step.id in regeneration_step_ids and step.id not in selected
        )
        target_steps.sort(key=lambda step: step.id)

    # Adopt unreferenced detail files before the regen gate runs. A step
    # whose ``detail:`` pointer was never persisted (typically a split that
    # renumbered a step whose pointer was already ``None`` — see
    # ``find_unreferenced_detail_for_step``) leaves its canonical file on
    # disk that the ``invoke_targets`` gate below would re-author through
    # Claude, clobbering it. Reattach the pointer so the idempotent skip
    # fires instead. Skipped under ``force`` (burn-it-all-down re-authors
    # regardless) and ``dry_run`` (no plan-file side effects).
    if not force and not dry_run:
        for step in target_steps:
            if step.detail is not None:
                continue
            adoptable = find_unreferenced_detail_for_step(
                plan_path, plan, step
            )
            if adoptable is None:
                continue
            rel = _repo_relative(adoptable, repo_root)
            try:
                update_step_detail_field(plan_path, step.id, rel)
            except DetailError as exc:
                tool(
                    f"step {step.id}: found unreferenced detail file {rel} "
                    f"but could not attach it ({exc})",
                    level="warning",
                )
                continue
            step.detail = rel
            tool(
                f"step {step.id}: adopted existing detail file {rel} "
                "(frontmatter pointer was unset)"
            )

    # Default to live stderr reporting; tests inject NullReporter. The
    # reporter is only consulted around the actual claude call — skip
    # paths and ``dry_run`` emit nothing because there's no work in
    # flight to report on.
    if reporter is None:
        reporter = StderrReporter()

    if prompt_fn is None:
        import builtins
        prompt_fn = builtins.input

    # Pre-scan: load any valid checkpoint per step *once* up front and
    # stash it. Two purposes:
    #
    # 1. The [N/M] counter must reflect the number of *invocations* — a
    #    step that resumes from cache (or one that's already done on
    #    disk) shouldn't inflate the denominator. Computing this ahead
    #    of the loop avoids the prior post-hoc decrement that produced
    #    a visibly inconsistent counter (``[1/3]`` then ``[2/2]``) when
    #    a resume happened mid-run.
    # 2. Avoid double I/O — the per-step branch reads ``cached_by_id``
    #    instead of re-calling ``load_if_valid``.
    #
    # If the user declines a resume prompt later (TTY only), the loop
    # bumps ``invoke_total`` back up so the denominator stays accurate.
    plan_slug = _plan_slug(plan_path)
    cached_by_id: dict[int, Optional[Checkpoint]] = {}
    for s in target_steps:
        # ``force`` is "burn it all down": both the file-exists skip
        # AND the cache hit are bypassed. Honoring a checkpoint under
        # ``--force`` would silently re-emit a stale body the user
        # explicitly asked to regenerate, which is the opposite of
        # the flag's stated semantics.
        if force or s.id in regeneration_step_ids or not resume:
            cached_by_id[s.id] = None
            continue
        scan_ckpt_path = checkpoint_path(
            repo_root,
            plan_slug,
            _DETAIL_CHECKPOINT_NAME.format(step_id=s.id),
        )
        scan_ckpt = load_if_valid(
            scan_ckpt_path,
            expected_input_hash=_detail_step_input_hash(
                plan_path, s, project_context=project_context
            ),
        )
        if scan_ckpt is not None and require_deferral_envelope:
            parsed_checkpoint = parse_structured_detail_response(
                scan_ckpt.payload,
                step=s,
                plan=plan,
                candidate_buckets=candidate_buckets,
            )
            if parsed_checkpoint is None:
                scan_ckpt = None
        cached_by_id[s.id] = scan_ckpt
        if run_logger is not None and scan_ckpt is not None:
            run_logger.checkpoint_hit(
                _DETAIL_CHECKPOINT_NAME.format(step_id=s.id),
                scan_ckpt.input_hash,
                len(scan_ckpt.payload.encode("utf-8")),
                step_id=s.id,
                path=_repo_relative(scan_ckpt_path, repo_root),
                created_at=scan_ckpt.created_at,
            )

    invoke_targets = [
        s for s in target_steps
        if (
            force
            or s.id in regeneration_step_ids
            or s.detail is None
            or not derive_detail_path(plan_path, plan, s).exists()
        )
        and cached_by_id[s.id] is None
    ]
    return _RunGradeDetailSetup(
        plan=plan,
        compute_plan_fingerprint=compute_plan_fingerprint,
        plan_fingerprint=plan_fingerprint,
        concept_tree=concept_tree,
        regeneration_step_ids=regeneration_step_ids,
        candidate_buckets=candidate_buckets,
        require_deferral_envelope=require_deferral_envelope,
        target_steps=target_steps,
        reporter=reporter,
        prompt_fn=prompt_fn,
        run_logger=run_logger,
        plan_slug=plan_slug,
        project_context=project_context,
        cached_by_id=cached_by_id,
        invoke_total=0 if dry_run else len(invoke_targets),
        invoke_idx=0,
    )


@dataclass(frozen=True)
class _StepDetailConvergenceOutcome:
    """The serial detail-quality loop's outcome for one durable detail."""

    detail_quality_clean: bool
    accepted_plan_edit: bool
    did_structural_split: bool
    structural_split_id: Optional[int]
    structural_recommendations: tuple["Recommendation", ...]


def _converge_run_grade_step_detail(
    *,
    step: Step,
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    plan_fingerprint: str,
    plan_slug: str,
    invoker: DetailInvoker,
    reporter: ProgressReporter,
    run_logger: Optional[RunLogWriter],
    budget: IterativeBudget,
    allow_drift: bool,
    auto_reconcile_on_drift: bool,
    collision_sidecar: bool,
    triage: bool,
    include_info: bool,
    allow_split: bool,
    prompt_fn: Callable[[str], str],
    structural_seen: set[str],
    project_context: str = "",
    recovery_only: bool = False,
) -> _StepDetailConvergenceOutcome:
    """Converge one written run-grade detail without post-loop policy.

    ``recovery_only`` forces this to a no-op regardless of ``budget`` —
    the convergence loop's detail-quality scan reaches
    :func:`collect_step_grounding_findings`, which (like
    :func:`_format_already_implemented_block`) reads every step's detail
    file and would raise ``DetailFormatError`` on an unrelated sibling's
    malformed marker. Targeted recovery never converges the step it just
    replaced; an operator re-runs ``--iterate`` separately once every
    refused file in the bundle is repaired.
    """
    detail_quality_clean = False
    accepted_plan_edit = False
    did_structural_split = False
    structural_split_id: Optional[int] = None
    structural_recommendations: list["Recommendation"] = []
    # --- iteration loop ---------------------------------------
    # Tighten the just-written detail body by feeding it through
    # detail-quality + apply_finding until convergence or budget
    # exhaustion. No-op when the effective step budget is disabled.
    #
    # Apply-finding edits the detail file in place via the
    # launcher's snapshot+diff path; iteration N+1's review runs
    # against iteration N's apply-output (re-read from disk by
    # collect_detail_quality_findings) so we don't need to
    # re-invoke render_detail_prompt. No per-iteration checkpoint
    # either — the on-disk detail file is the durable artifact;
    # an interrupted mid-loop run leaves a partially-iterated
    # body that the next `plan-tool detail` run skips entirely
    # (already has step.detail set and file exists). Operators
    # who want to re-iterate pass --force.
    step_budget = _scaled_detail_budget_for_step(step, budget)
    if step_budget.enabled and not recovery_only:
        plan_slug_for_iter = plan_slug
        # Watch only step.files for drift, NOT plan + detail
        # (those are apply_finding's legitimate edit targets every
        # iteration). ``iteration_session`` releases the lock and
        # restores the SIGINT handler on EVERY exit path, including
        # an unexpected exception escaping the loop body -- so a
        # crashed detail loop no longer leaks the lockfile.
        from plan_tool.scope_guard import (
            build_file_to_step_map,
            compute_drift_watched_paths as _cdwp,
        )
        _file_to_step = build_file_to_step_map(plan, repo_root)
        _watched_paths = _cdwp(plan, plan_path, repo_root)

        # Reuse the one best-effort fingerprint computed at entry.
        _apply_verdict_plan_fp = plan_fingerprint

        from plan_tool.drift_detection import iteration_session
        with iteration_session(
            repo_root,
            enabled=True,
            slug=plan_slug_for_iter,
            command=f"detail-step{step.id}",
            loop_name=f"detail (step {step.id})",
            watched_paths=_watched_paths,
            file_to_step=_file_to_step,
        ) as _iter_lock:
                # Entry banner: name the loop's actual job (detail-quality
                # audit -> apply -> reaudit, driving findings to zero) so
                # operators don't confuse it with the post-loop lessons-
                # distillation pass that runs after the loop exits. When
                # the initial scan returns zero findings the loop breaks
                # immediately and the next visible claude call is that
                # distillation pass; a misnamed banner here makes the
                # distillation look like the loop's main work.
                # Indented under the step header so the convergence loop
                # banner visually nests with the step it belongs to.
                # ``plan-tool:`` prefix dropped — these informational
                # lines aren't claude output, so the distinction the
                # prefix used to carry is no longer needed (raw claude
                # output is gated behind ``--debug``).
                print(
                    f"        detail-quality: starting convergence loop "
                    f"(max {step_budget.max_iterations} iter, "
                    f"{step_budget.budget_seconds}s no-progress deadline)",
                    file=sys.stderr,
                )
                state = ConvergenceState(budget=step_budget)
                initial_findings = _cached_purity_findings(
                    plan_path,
                    step,
                    repo_root=repo_root,
                    plan_name=plan_slug_for_iter,
                    invoker=invoker,
                    # Write-through: the authoring loop always calls
                    # Claude (never skips) and refreshes the purity cache
                    # for the audit path to reuse — grounding against
                    # current code is never served from cache here.
                    read_through=False,
                    # The initial discovery scan is iteration 1, not 0 —
                    # operators read it as the first iteration's scan, so
                    # the loop re-scans below carry on from 2 (+2 offset).
                    iteration=1,
                    max_iterations=step_budget.max_iterations,
                    reporter=reporter,
                    run_logger=run_logger,
                    project_context=project_context,
                )
                open_findings = list(initial_findings)
                # Surface the gaps this scan found, with severity, the
                # same way completeness-audit does (the initial scan is
                # iteration 1, matching its ``/ scan`` reporter line).
                emit_detail_findings_summary(
                    open_findings, step_id=step.id, iteration=1,
                )
                # Seed convergence with the apply-eligible subset
                # only (see _apply_eligible_ids); deferred findings
                # are surfaced but excluded from the marginal/stall
                # math so they can't stop the loop prematurely.
                state.current_finding_ids = _apply_eligible_ids(
                    open_findings, triage=triage,
                    include_info=include_info,
                )
                # Fingerprints (rec.id) already dispatched to
                # apply_finding this loop. A finding is applied at most
                # once: re-applying the identical guidance that already
                # ran won't resolve it — it just re-spends tokens and a
                # full re-scan every round (the 27-dispatch / 3-net churn
                # #74 measured). Mirrors completeness's
                # ``applied_fingerprints``; the rec stays in
                # ``open_findings`` (convergence math + the final
                # open-count still see it), only re-*dispatch* is gated.
                applied_fingerprints: set[str] = set()
                # Drift-halt sentinel. Set inside the for-rec loop on
                # pre- or post-apply drift; the outer while checks it
                # and exits, leaving the lock release + drift-warning
                # emit (below) to fire normally.
                detail_drift_halted = False
                # Structural-halt sentinel (trigger 2): set inside the
                # for-rec loop when a BLOCKED-STRUCTURAL apply escalates
                # to an applied split; the outer while checks it and
                # exits so the renumbered halves are re-authored post-loop.
                detail_structural_halted = False
                # Parse-halt sentinel. Set when apply_finding introduced
                # an unparseable plan and the helper restored the
                # pre-apply snapshot; further applies would wedge.
                detail_parse_halted = False
                # Collapse-tracking for repeated triage-deferral
                # blocks: the last reported (non-empty) deferred id
                # set and the iteration that reported it, so an
                # unchanged set on the next pass prints one delta
                # line instead of the full per-finding block.
                last_deferred_ids: Optional[frozenset[str]] = None
                last_deferred_iter = 0
                # Reset the no-progress timer: it was stamped at state
                # construction, before the minutes-long initial scan
                # above. Without this, a slow scan trips the deadline
                # before the loop applies anything. budget_seconds
                # measures iteration progress, not the initial scan.
                touch(state)
                while True:
                    cont, reason = should_continue(state)
                    if not cont:
                        bar = "─" * 60
                        # Report the full open set (apply-eligible +
                        # deferred) so the operator sees everything
                        # left, even though convergence tracks only
                        # the apply-eligible ids.
                        open_count = len(open_findings)
                        # Apply-then-empty exits here via
                        # ``should_continue`` → ``converged``, not the
                        # empty-``open_apply`` branch below — mark clean
                        # so lesson capture sees the fixed body.
                        if reason == "converged" and open_count == 0:
                            detail_quality_clean = True
                        hints: list[str] = []
                        if open_count > 0:
                            hints.append(
                                f"  plan-tool reconcile-plan-walk "
                                f"{plan_slug_for_iter}   "
                                f"# interactively review the "
                                f"{open_count} open finding(s)"
                            )
                            hints.append(
                                f"  plan-tool detail "
                                f"{plan_slug_for_iter} --step {step.id} "
                                f"--force   "
                                f"# re-author this step's detail "
                                f"from scratch"
                            )
                        if reason == "deadline_exceeded":
                            hints.append(
                                f"  plan-tool detail "
                                f"{plan_slug_for_iter} --step {step.id} "
                                f"--iteration-budget "
                                f"{larger_iteration_budget_seconds(state.budget.budget_seconds)}   "
                                f"# resume with a longer no-progress deadline"
                            )
                        elif reason == "max_iterations":
                            hints.append(
                                f"  plan-tool detail "
                                f"{plan_slug_for_iter} --step {step.id} "
                                f"--max-iterations 5   "
                                f"# resume with a larger iteration cap"
                            )
                        elif reason == "time_budget_exceeded":
                            hints.append(
                                f"  plan-tool detail "
                                f"{plan_slug_for_iter} --step {step.id}   "
                                f"# time budget reached — stopped cleanly "
                                f"at a round boundary (this step's authored "
                                f"detail is durable). Re-run to continue, "
                                f"or raise --time-budget."
                            )
                        hint_block = (
                            "\n  What to do:\n" + "\n".join(hints)
                            if hints else ""
                        )
                        print(
                            f"\n{bar}\n"
                            f"  detail iteration loop stopped "
                            f"for step {step.id}: {reason}\n"
                            f"  iteration={state.iteration} · "
                            f"open_findings={open_count}"
                            f"{hint_block}\n"
                            f"{bar}",
                            file=sys.stderr,
                        )
                        break
                    # Impact-weighted triage (session 4 follow-up).
                    from plan_tool.review import (
                        emit_triage_summary,
                        partition_findings_for_triage,
                    )
                    open_apply, open_deferred = (
                        partition_findings_for_triage(
                            open_findings, triage_enabled=triage,
                            include_info=include_info,
                        )
                    )
                    # Dedup: drop apply-eligible findings already
                    # dispatched this run. ``retry_blocked`` is the set
                    # held back so the empty-``open_apply`` branch below
                    # can tell true convergence (nothing left) from
                    # dedup-exhaustion (everything left was already
                    # tried) and stop re-scanning either way.
                    retry_blocked = [
                        r for r in open_apply
                        if r.id in applied_fingerprints
                    ]
                    open_apply = [
                        r for r in open_apply
                        if r.id not in applied_fingerprints
                    ]
                    if open_deferred:
                        current_iter = state.iteration + 1
                        report = summarize_deferral_delta(
                            open_deferred,
                            previous_ids=last_deferred_ids,
                            previous_iteration=last_deferred_iter,
                        )
                        if report.collapsed:
                            print(
                                f"        detail-quality: {report.line}",
                                file=sys.stderr,
                            )
                        else:
                            emit_triage_summary(
                                open_deferred,
                                iteration_label=(
                                    f"detail step {step.id} iter "
                                    f"{current_iter}"
                                ),
                            )
                            if report.line:
                                print(
                                    f"        detail-quality: "
                                    f"{report.line}",
                                    file=sys.stderr,
                                )
                        last_deferred_ids = frozenset(
                            rec.id for rec in open_deferred
                        )
                        last_deferred_iter = current_iter
                    if not open_apply:
                        if retry_blocked:
                            # Every apply-eligible finding left was
                            # already dispatched this run and didn't
                            # resolve. An identical re-apply won't help,
                            # so stop re-scanning and surface them as
                            # open (the exit report lists open_findings).
                            tool(
                                f"detail iteration halting -- all "
                                f"{len(retry_blocked)} remaining apply-"
                                f"eligible finding(s) for step {step.id} "
                                f"were already applied this run and did "
                                f"not resolve; surfaced as open for "
                                f"manual review."
                            )
                        elif open_deferred:
                            tool(
                                f"detail iteration halting "
                                f"-- all {len(open_deferred)} remaining "
                                f"finding(s) for step {step.id} are "
                                f"triaged-deferred. Apply manually or "
                                f"pass --no-triage to force-apply."
                            )
                        else:
                            # No findings to apply and none deferred. Name
                            # the silence so the post-loop lessons-distill
                            # line doesn't look like the convergence loop's
                            # main work; otherwise this branch breaks with
                            # zero on-screen signal between the entry
                            # banner and the distillation pass.
                            print(
                                f"        detail-quality: converged "
                                f"(0 findings at iter "
                                f"{state.iteration}); skipping apply pass",
                                file=sys.stderr,
                            )
                            detail_quality_clean = True
                        break
                    for rec in open_apply:
                        # Pre-apply drift check (task #30 -> #33). Halt
                        # before spending claude tokens on a likely-
                        # spurious apply when a watched (step.files)
                        # file was edited between applies. Mirrors
                        # cmd_completeness.
                        if not allow_drift:
                            from plan_tool.drift_detection import (
                                check_drift as _check_drift,
                                emit_drift_halt_warning as _emit_halt,
                            )
                            pre_drifted = _check_drift(_iter_lock)
                            if pre_drifted:
                                _emit_halt(
                                    pre_drifted,
                                    phase="before",
                                    finding_id=rec.id,
                                    repo_root=repo_root,
                                    file_to_step=_file_to_step,
                                )
                                if auto_reconcile_on_drift:
                                    from plan_tool.auto_reconcile import (
                                        run_auto_reconcile_on_drift,
                                    )
                                    run_auto_reconcile_on_drift(
                                        drifted=pre_drifted,
                                        file_to_step=_file_to_step,
                                        plan_path=plan_path,
                                        plan_slug=plan_slug_for_iter,
                                        repo_root=repo_root,
                                        run_logger=run_logger,
                                    )
                                detail_drift_halted = True
                                break

                        # Wrap the apply in an ``apply_finding_dispatch``
                        # phase recording the finding ``source`` so a run
                        # log can price detail's per-finding applies (the
                        # loop previously left these calls unlogged).
                        if run_logger is not None:
                            run_logger.phase_start(
                                "apply_finding_dispatch",
                                step_id=step.id,
                                source=rec.source,
                                finding_label=next(
                                    (ln.strip()
                                     for ln in rec.body.splitlines()
                                     if ln.strip()),
                                    rec.source,
                                ),
                            )
                        _apply_t0 = time.monotonic()
                        apply_context_plan = parse_plan(plan_path)
                        risk_context_block = render_declared_risk_context(
                            apply_context_plan
                        )
                        apply_result = apply_finding(
                            plan_path,
                            repo_root=repo_root,
                            finding_body=format_recommendation_for_apply(rec),
                            step_id=step.id,
                            plan_name=plan_slug_for_iter,
                            auto_fix_introduced=True,
                            # Opt into the BLOCKED-STRUCTURAL verdict
                            # (step 3's flag, default OFF) so the rendered
                            # apply-finding prompt offers it and the
                            # trigger-2 branch below has a verdict to route.
                            allow_structural_verdict=True,
                            run_logger=run_logger,
                            anchor=(rec.anchor or ""),
                            plan_fingerprint=_apply_verdict_plan_fp,
                            risk_context_block=risk_context_block,
                        )
                        apply_reverted = revert_apply_if_parse_broken(apply_result)
                        if run_logger is not None:
                            run_logger.phase_end(
                                "apply_finding_dispatch",
                                int((time.monotonic() - _apply_t0) * 1000),
                                (
                                    "reverted" if apply_reverted
                                    else apply_result.verdict.lower()
                                ),
                                step_id=step.id,
                                source=rec.source,
                                verdict=(
                                    "REVERTED" if apply_reverted
                                    else apply_result.verdict
                                ),
                            )
                        if apply_reverted:
                            warn(
                                "reverted apply-finding edits: post-edit "
                                "plan failed to parse (keeping would wedge "
                                "the detail iterate loop); fix the YAML "
                                "and re-run"
                            )
                            detail_parse_halted = True
                            break
                        if apply_result.verdict == "APPLIED":
                            accepted_plan_edit = True
                        # Each apply_finding can take 10-15 min;
                        # debounce the deadline timer.
                        touch(state)
                        # Mark dispatched regardless of verdict (tokens
                        # are spent; an identical re-apply won't resolve
                        # it). Gates re-dispatch on later rounds.
                        applied_fingerprints.add(rec.id)

                        # Trigger 2: Claude decided mid-apply that the
                        # only correct fix is a refactor+feature split and
                        # emitted ``BLOCKED-STRUCTURAL`` (step 3's verdict,
                        # offered here via ``allow_structural_verdict``).
                        # Route it to the split bridge. The ordering below
                        # IS the contract: revert the partial edit first
                        # (apply_finding only reverts on a non-zero exit,
                        # so a BLOCKED-STRUCTURAL run may leave a half-
                        # applied prose edit, and escalate_to_split re-reads
                        # the plan from disk), then dedup, then escalate.
                        # The drift check below is irrelevant on this path
                        # — the edit is reverted.
                        if apply_result.verdict == "BLOCKED-STRUCTURAL":
                            from plan_tool.launcher import (
                                _restore_text_files as _revert_snapshot,
                            )
                            _revert_snapshot(apply_result.pre_snapshot)
                            # One escalation/proposal per finding across
                            # the run's convergence iterations — the cost/
                            # termination guard. The underlying
                            # apply_finding may still re-run on the same
                            # finding until stall detection ends the loop;
                            # this bounds re-escalation, not re-invocation.
                            if rec.id in structural_seen:
                                continue
                            structural_seen.add(rec.id)
                            esc = escalate_to_split(
                                plan_path,
                                step_id=step.id,
                                repo_root=repo_root,
                                invoker=invoker,
                                allow_split=allow_split,
                                prompt_fn=prompt_fn,
                            )
                            if esc.outcome == "applied":
                                # The split renumbered ids out from under
                                # all three loops; break every level and
                                # re-author the halves post-loop. Remaining
                                # open_apply recs belong to an id that no
                                # longer exists.
                                structural_split_id = esc.target_id or step.id
                                detail_structural_halted = True
                                did_structural_split = True
                                break
                            # Every non-applied outcome surfaces some
                            # operator-visible signal (invariant 1) —
                            # never a silent skip — bounded to one per
                            # finding by ``structural_seen`` above.
                            if esc.outcome == "recommended":
                                if esc.recommendation is not None:
                                    structural_recommendations.append(
                                        esc.recommendation
                                    )
                            elif esc.outcome == "unsafe":
                                tool(
                                    f"structural escalation unsafe — "
                                    f"downstream steps {esc.blocking} are "
                                    "done; resolve them, then run "
                                    "plan-tool split",
                                    level="warning",
                                )
                            else:
                                # proposal-unusable / step-missing — both
                                # carry recommendation=None.
                                tool(
                                    f"structural finding {rec.id} on step "
                                    f"{step.id}: escalate_to_split returned "
                                    f"{esc.outcome}; nothing surfaced to "
                                    "apply — re-run or re-plan",
                                    level="note",
                                )
                            continue

                        # Post-apply drift check. KEEP this apply's
                        # edits (tokens spent; may still be useful)
                        # but halt subsequent applies.
                        if not allow_drift:
                            from plan_tool.drift_detection import (
                                check_drift as _check_drift,
                                emit_drift_halt_warning as _emit_halt,
                            )
                            post_drifted = _check_drift(_iter_lock)
                            if post_drifted:
                                _emit_halt(
                                    post_drifted,
                                    phase="during",
                                    finding_id=rec.id,
                                    repo_root=repo_root,
                                    file_to_step=_file_to_step,
                                )
                                # Change-collision sidecar +
                                # pause-for-merge. On merge+continue,
                                # break the for-rec loop without
                                # setting ``detail_drift_halted`` so
                                # the outer while reiterates against
                                # the merged state. On decline /
                                # headless / Ctrl-C, fall through to
                                # the legacy halt path.
                                if collision_sidecar:
                                    from plan_tool.change_collision import (
                                        handle_drift_collision,
                                    )
                                    if handle_drift_collision(
                                        apply_result.pre_snapshot,
                                        repo_root=repo_root,
                                    ):
                                        # Refresh the lock's content-
                                        # hash snapshot so the next
                                        # iteration's pre-apply check
                                        # compares against the merged
                                        # state (Bug 1 from session-4
                                        # review).
                                        from plan_tool.drift_detection import (
                                            refresh_snapshot,
                                        )
                                        refresh_snapshot(_iter_lock)
                                        break
                                if auto_reconcile_on_drift:
                                    from plan_tool.auto_reconcile import (
                                        run_auto_reconcile_on_drift,
                                    )
                                    run_auto_reconcile_on_drift(
                                        drifted=post_drifted,
                                        file_to_step=_file_to_step,
                                        plan_path=plan_path,
                                        plan_slug=plan_slug_for_iter,
                                        repo_root=repo_root,
                                        run_logger=run_logger,
                                    )
                                detail_drift_halted = True
                                break

                    if detail_drift_halted:
                        break
                    if detail_parse_halted:
                        break
                    # Structural halt has its own post-loop handling
                    # (re-author the renumbered halves) — keep it
                    # separate from the drift halt above.
                    if detail_structural_halted:
                        break

                    open_findings = _cached_purity_findings(
                        plan_path,
                        step,
                        repo_root=repo_root,
                        plan_name=plan_slug_for_iter,
                        invoker=invoker,
                        # Write-through (see the initial scan above): the
                        # re-scan always calls Claude and refreshes the
                        # cache; it never returns a cached verdict.
                        read_through=False,
                        # +2, not +1: the initial scan claimed iter 1, and
                        # state.iteration is still 0 on the first re-scan.
                        iteration=state.iteration + 2,
                        max_iterations=step_budget.max_iterations,
                        reporter=reporter,
                        run_logger=run_logger,
                        project_context=project_context,
                    )
                    # Same severity-tagged gap list as the initial scan
                    # (iteration label matches the re-scan's ``/ scan``
                    # reporter line: +2 over state.iteration).
                    emit_detail_findings_summary(
                        open_findings,
                        step_id=step.id,
                        iteration=state.iteration + 2,
                    )
                    record_iteration(
                        state,
                        _apply_eligible_ids(
                            open_findings, triage=triage,
                            include_info=include_info,
                        ),
                    )

    return _StepDetailConvergenceOutcome(
        detail_quality_clean=detail_quality_clean,
        accepted_plan_edit=accepted_plan_edit,
        did_structural_split=did_structural_split,
        structural_split_id=structural_split_id,
        structural_recommendations=tuple(structural_recommendations),
    )


@dataclass(frozen=True)
class _RunGradeDetailLifecycleResult:
    """Run-grade authoring state handed to later post-loop phases."""

    results: list[DetailResult]
    mixed_steps: list[tuple[int, "Recommendation"]]
    structural_split_ids: set[int]
    inloop_structural_recs: list["Recommendation"]


@dataclass(frozen=True)
class _PhaseBSplitContext:
    """Dependencies Phase B needs to resolve and recover mixed-step splits."""

    plan_path: Path
    repo_root: Path
    invoker: DetailInvoker
    reporter: ProgressReporter
    extract_lessons: bool
    lessons_invoker: Optional[LessonsInvoker]
    foundational_invoker: Optional[SweepInvoker]
    strict_check: bool
    equivalence_invoker: Optional[EquivalenceInvoker]
    prompt_fn: Callable[[str], str]
    run_logger: Optional[RunLogWriter]
    budget: IterativeBudget
    allow_drift: bool
    auto_reconcile_on_drift: bool
    collision_sidecar: bool
    triage: bool
    include_info: bool
    allow_split: bool
    plan_slug: str


@dataclass(frozen=True)
class _Trigger2SplitContext:
    """Dependencies Trigger 2 needs to recover in-loop structural splits."""

    plan_path: Path
    repo_root: Path
    invoker: DetailInvoker
    reporter: ProgressReporter
    extract_lessons: bool
    lessons_invoker: Optional[LessonsInvoker]
    foundational_invoker: Optional[SweepInvoker]
    strict_check: bool
    equivalence_invoker: Optional[EquivalenceInvoker]
    prompt_fn: Callable[[str], str]
    run_logger: Optional[RunLogWriter]
    budget: IterativeBudget
    allow_drift: bool
    auto_reconcile_on_drift: bool
    collision_sidecar: bool
    triage: bool
    include_info: bool
    plan_slug: str


def _handle_phase_b_splits(
    results: list[DetailResult],
    *,
    mixed_steps: list[tuple[int, "Recommendation"]],
    applied_in_loop_split_ids: set[int],
    context: _PhaseBSplitContext,
) -> list[DetailResult]:
    """Resolve mixed-step splits before Trigger 2 handles its own state."""
    eligible_mixed_steps = [
        (step_id, finding)
        for step_id, finding in mixed_steps
        if step_id not in applied_in_loop_split_ids
    ]
    if not eligible_mixed_steps:
        return results

    split_target_ids: set[int] = set()
    structural_recs: list[Recommendation] = []
    for target_id, _finding in sorted(
        eligible_mixed_steps, key=lambda item: item[0], reverse=True
    ):
        result = escalate_to_split(
            context.plan_path,
            step_id=target_id,
            repo_root=context.repo_root,
            invoker=context.invoker,
            allow_split=context.allow_split,
            prompt_fn=context.prompt_fn,
        )
        if result.outcome == "unsafe":
            tool(
                f"step {target_id}: cannot recommend split — downstream "
                f"step(s) {result.blocking} are done; "
                "restructure via re-plan if the split is still wanted",
                level="warning",
            )
            continue
        if result.outcome == "proposal-unusable":
            tool(
                f"step {target_id}: split proposal was unusable; "
                "leaving the step as-is",
                level="note",
            )
            continue
        if result.outcome == "applied":
            split_target_ids.add(target_id)
            tool(
                f"step {target_id}: split into refactor + feature; "
                "re-authoring both halves",
                level="note",
            )
            continue
        if result.outcome == "recommended":
            if result.recommendation is not None:
                structural_recs.append(result.recommendation)
            continue
        # A lower target can be renumbered away by an earlier split.

    if split_target_ids:
        half_ids = [
            step.id
            for step in parse_plan(context.plan_path).steps
            if step.detail is None
        ]
        half_results: list[DetailResult] = []
        for half_id in half_ids:
            half_results.extend(
                generate_detail(
                    context.plan_path,
                    repo_root=context.repo_root,
                    step_id=half_id,
                    force=False,
                    invoker=context.invoker,
                    reporter=context.reporter,
                    extract_lessons=context.extract_lessons,
                    lessons_invoker=context.lessons_invoker,
                    foundational_invoker=context.foundational_invoker,
                    strict_check=context.strict_check,
                    equivalence_invoker=context.equivalence_invoker,
                    resume=False,
                    prompt_fn=context.prompt_fn,
                    run_logger=context.run_logger,
                    budget=context.budget,
                    allow_drift=context.allow_drift,
                    auto_reconcile_on_drift=context.auto_reconcile_on_drift,
                    collision_sidecar=context.collision_sidecar,
                    triage=context.triage,
                    include_info=context.include_info,
                    allow_split=False,
                )
            )

        written_keys = {
            _detail_slug_key(Path(result.output_path))
            for result in results
            if result.written
        }
        written_keys |= {
            _detail_slug_key(Path(result.output_path))
            for result in half_results
            if result.written
        }
        minimum_split_id = min(split_target_ids)
        rebuilt_results = [
            result for result in results if result.step_id < minimum_split_id
        ]
        for step in parse_plan(context.plan_path).steps:
            if step.id < minimum_split_id or not step.detail:
                continue
            output_path = context.repo_root / step.detail
            if not output_path.is_file():
                continue
            if _detail_slug_key(output_path) in written_keys:
                rebuilt_results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=True,
                    )
                )
            else:
                rebuilt_results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=False,
                        skipped_reason=(
                            "already exists (carried through split renumber)"
                        ),
                    )
                )
        # Keep failed child results so a nested persistence failure remains
        # visible after rebuilding the renumbered region.
        rebuilt_results.extend(result for result in half_results if not result.written)
        results = rebuilt_results

    if structural_recs:
        _emit_split_recommendations(
            structural_recs,
            plan_slug=context.plan_slug,
        )
    return results


def _handle_trigger_2_splits(
    results: list[DetailResult],
    *,
    structural_split_ids: set[int],
    inloop_structural_recs: list["Recommendation"],
    context: _Trigger2SplitContext,
) -> list[DetailResult]:
    """Recover in-loop splits after Phase B and emit their recommendations."""
    if structural_split_ids:
        detail_less_step_ids = [
            step.id
            for step in parse_plan(context.plan_path).steps
            if step.detail is None
        ]
        recovered_results: list[DetailResult] = []
        for step_id in detail_less_step_ids:
            # Recovered halves join the enclosing run's final commit.
            recovered_results.extend(
                generate_detail(
                    context.plan_path,
                    repo_root=context.repo_root,
                    step_id=step_id,
                    force=False,
                    invoker=context.invoker,
                    reporter=context.reporter,
                    extract_lessons=context.extract_lessons,
                    lessons_invoker=context.lessons_invoker,
                    foundational_invoker=context.foundational_invoker,
                    strict_check=context.strict_check,
                    equivalence_invoker=context.equivalence_invoker,
                    resume=False,
                    prompt_fn=context.prompt_fn,
                    run_logger=context.run_logger,
                    budget=context.budget,
                    allow_drift=context.allow_drift,
                    auto_reconcile_on_drift=context.auto_reconcile_on_drift,
                    collision_sidecar=context.collision_sidecar,
                    triage=context.triage,
                    include_info=context.include_info,
                    allow_split=False,
                )
            )

        written_keys = {
            _detail_slug_key(Path(result.output_path))
            for result in results
            if result.written
        }
        written_keys |= {
            _detail_slug_key(Path(result.output_path))
            for result in recovered_results
            if result.written
        }
        minimum_split_id = min(structural_split_ids)
        rebuilt_results = [
            result for result in results if result.step_id < minimum_split_id
        ]
        for step in parse_plan(context.plan_path).steps:
            if step.id < minimum_split_id or not step.detail:
                continue
            output_path = context.repo_root / step.detail
            if not output_path.is_file():
                continue
            if _detail_slug_key(output_path) in written_keys:
                rebuilt_results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=True,
                    )
                )
            else:
                rebuilt_results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=False,
                        skipped_reason=(
                            "already exists (carried through split renumber)"
                        ),
                    )
                )
        # Keep failed child results so nested persistence failures remain
        # visible after rebuilding the renumbered region.
        rebuilt_results.extend(
            result for result in recovered_results if not result.written
        )
        results = rebuilt_results

    if inloop_structural_recs:
        _emit_split_recommendations(
            inloop_structural_recs,
            plan_slug=context.plan_slug,
        )
    return results


def _persist_final_detail_concepts(
    results: list[DetailResult],
    *,
    dry_run: bool,
    plan_path: Path,
    concept_tree: Optional[ConceptTree],
    candidate_buckets: dict[str, str],
    compute_plan_fingerprint: Callable[[Path], str],
) -> list[DetailResult]:
    """Persist final run-grade deferrals after this invocation's handlers."""
    # Workers and post-loop handlers publish only detail files; persist the
    # concept-record side effect once here, in deterministic final-result order.
    # A failed step is absent from ``written_replacements`` so its old state
    # remains as an explicit recovery signal.
    if dry_run:
        return results

    written_replacements = [
        (result.step_id, result.deferrals)
        for result in results
        if result.written
    ]
    new_deferrals = [
        deferral
        for _step_id, deferrals in written_replacements
        for deferral in deferrals
    ]

    if (
        concept_tree is not None
        and concept_tree.record_kind == RECORD_KIND_FULL_TREE
    ):
        # Legacy full-tree record: preserve its include-regeneration link
        # machinery, but never record a fresh flat deferral into it — warn
        # so the model's proposal reaches a human (recording into a legacy
        # record is BACKLOG #131), and drop the unrecordable flat deferrals
        # so the link replacement never indexes a missing node.
        for deferral in new_deferrals:
            warn(
                f"step {deferral.step_id}: proposed deferral of "
                f"`{deferral.concept_id}` cannot be recorded on this plan's "
                "legacy full-tree concept record; migrate the record "
                "(BACKLOG #131) to capture the deferral."
            )
        link_replacements = [
            (step_id, ()) for step_id, _deferrals in written_replacements
        ]
        if link_replacements:
            updated_concepts = _replace_detail_deferrals(
                concept_tree, link_replacements
            )
            # Detail writes change the bundle included in the concept
            # fingerprint. This persistence-only refresh is best-effort;
            # the entry fingerprint above remains the shared telemetry key.
            try:
                updated_concepts.plan_fingerprint = compute_plan_fingerprint(
                    plan_path
                )
            except Exception:
                return results
            return _persist_concepts_or_mark_failed(
                plan_path, updated_concepts, results
            )
        return results

    if not new_deferrals:
        return results

    # Record-absent or existing decision-record: record each newly deferred
    # body-section bucket as a flat, unreviewed ``defer`` node.
    try:
        final_plan_fingerprint = compute_plan_fingerprint(plan_path)
    except Exception:
        return results
    record = _record_flat_deferrals(
        concept_tree,
        new_deferrals,
        candidate_buckets,
        plan_path,
        final_plan_fingerprint,
    )
    return _persist_concepts_or_mark_failed(plan_path, record, results)


def _run_grade_detail_lifecycle(
    *,
    prepared: _RunGradeDetailSetup,
    plan_path: Path,
    repo_root: Path,
    force: bool,
    dry_run: bool,
    invoker: DetailInvoker,
    extract_lessons: bool,
    lessons_invoker: Optional[LessonsInvoker],
    foundational_invoker: Optional[SweepInvoker],
    capture_scenarios: bool,
    arm: Optional[str],
    strict_check: bool,
    equivalence_invoker: Optional[EquivalenceInvoker],
    budget: IterativeBudget,
    allow_drift: bool,
    auto_reconcile_on_drift: bool,
    collision_sidecar: bool,
    triage: bool,
    include_info: bool,
    allow_split: bool,
    jobs: int,
    commit_step: Optional[Callable[[int, str], None]],
    prior_body: str,
    recovery_only: bool = False,
) -> _RunGradeDetailLifecycleResult:
    """Author prepared run-grade details through one serial or concurrent path.

    ``recovery_only`` is the targeted-recovery signal from
    ``detail --recover-refused``: the serial per-step loop discovers no
    siblings and renders the prompt with ``recovery_only=True`` (which skips
    the already-implemented scan), and the post-write convergence loop is
    forced off. It never reaches the concurrent path — ``--step N`` is
    single-target, so ``invoke_total`` is at most 1 and ``run_concurrent``
    below is always False.
    """
    plan = prepared.plan
    plan_fingerprint = prepared.plan_fingerprint
    concept_tree = prepared.concept_tree
    regeneration_step_ids = prepared.regeneration_step_ids
    candidate_buckets = prepared.candidate_buckets
    require_deferral_envelope = prepared.require_deferral_envelope
    target_steps = prepared.target_steps
    reporter = prepared.reporter
    prompt_fn = prepared.prompt_fn
    run_logger = prepared.run_logger
    plan_slug = prepared.plan_slug
    project_context = prepared.project_context
    cached_by_id = prepared.cached_by_id
    invoke_total = prepared.invoke_total
    invoke_idx = prepared.invoke_idx
    results: list[DetailResult] = []
    # Mixed (refactor + feature) steps the authoring purity self-check flags,
    # collected for the post-loop interactive split pass (Phase B). Always
    # accumulated (cheap); only acted on when ``allow_split`` is set.
    mixed_steps: "list[tuple[int, Recommendation]]" = []
    # Trigger-2 (in-loop ``BLOCKED-STRUCTURAL``) accumulators. Named distinctly
    # from Phase B's ``structural_recs`` — both live in this same
    # lifecycle scope, so a shared name would let Phase B's
    # ``structural_recs = []`` re-init silently discard these collected recs.
    structural_seen: set[str] = set()  # rec.ids already escalated this run
    structural_split_ids: set[int] = set()  # original ids split in-loop
    inloop_structural_recs: "list[Recommendation]" = []  # recommend-only recs

    # Concurrent-dispatch fork. Take it only when the operator asked for
    # overlap (``jobs > 1``), there is real work to author (more than one
    # fresh invoke — a single explicit ``--step`` or a fully-cached/already-
    # done run has at most one, so nothing to overlap), and there are no
    # writes to render inert (``dry_run``). The ``--iterate`` / ``--split``
    # arms were already refused above, so the concurrent path never runs the
    # convergence loop or an auto-split; it populates ``results`` /
    # ``mixed_steps`` and leaves the serial loop below a no-op. Phase B (which
    # only recommends when ``allow_split`` is False) still runs after it.
    run_concurrent = (
        jobs > 1 and not dry_run and invoke_total > 1
    )
    if run_concurrent:
        c_results, c_mixed = _generate_detail_concurrent(
            plan=plan,
            plan_path=plan_path,
            repo_root=repo_root,
            target_steps=target_steps,
            cached_by_id=cached_by_id,
            plan_slug=plan_slug,
            jobs=jobs,
            force=force,
            reporter=reporter,
            run_logger=run_logger,
            invoker=invoker,
            prompt_fn=prompt_fn,
            capture_scenarios=capture_scenarios,
            arm=arm,
            foundational_invoker=foundational_invoker,
            extract_lessons=extract_lessons,
            lessons_invoker=lessons_invoker,
            strict_check=strict_check,
            equivalence_invoker=equivalence_invoker,
            prior_body=prior_body,
            concept_tree=concept_tree,
            candidate_buckets=candidate_buckets,
            require_deferral_envelope=require_deferral_envelope,
            project_context=project_context,
        )
        results.extend(c_results)
        mixed_steps.extend(c_mixed)
    serial_steps = [] if run_concurrent else target_steps
    for step in serial_steps:
        # An earlier iteration's accepted apply-finding edit may have
        # reassigned ``plan`` (below, after ``_converge_run_grade_step_detail``)
        # to a fresh parse that touches this later step's own frontmatter —
        # not just the risk declaration the refresh exists for (the class
        # sweep an apply is explicitly allowed to make). Re-resolve ``step``
        # from that current plan so it never renders a prompt against a
        # title/intent/files snapshot older than the ``plan`` object driving
        # the rest of this iteration. A structural split (the only thing
        # that removes a step id) unconditionally ``break``s this loop
        # (below) before a later iteration can ever reach here with a
        # renumbered id, so an unresolvable id is a genuine invariant
        # violation, not a reachable case to fall back on.
        step = plan.step_by_id(step.id)
        output_path = derive_detail_path(plan_path, plan, step)

        if (
            not force
            and step.id not in regeneration_step_ids
            and step.detail is not None
            and output_path.exists()
        ):
            # Interactive prompt (TTY only) gives the user a chance to
            # replace the existing detail file instead of the historical
            # silent skip. Non-TTY callers (CI, piped) auto-decline, so
            # the idempotent "already exists → skip" behavior is
            # preserved for scripted use. The "already exists" substring
            # in ``skipped_reason`` is load-bearing — ``cmd_detail``
            # checks it to decide whether the skip flags the run.
            if not _confirm_replace(
                prompt_fn,
                step_id=step.id,
                step_title=step.title,
                output_path=output_path,
            ):
                results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=False,
                        skipped_reason=(
                            "already exists (user declined replace; pass "
                            "--force to skip the prompt and overwrite)"
                        ),
                    )
                )
                continue
            # User opted to replace; fall through to the normal
            # generation path. ``_archive_existing_detail`` will move
            # the current file aside right before the new body is
            # written so the prior content is preserved.

        # Under targeted recovery, discover no siblings at all — the point is
        # to never read (and validate the format version of) any other file
        # in the bundle, refused or not.
        siblings = () if recovery_only else _discover_siblings(output_path)
        # Render once per step before the optional sweep: this fence grounds
        # its classification and the authoring prompt with identical context.
        scope_fence_block = render_scope_fence(
            plan_path,
            plan_intent=plan.intent or "",
            step_intent=step.intent or "",
        )
        # Foundational-logic sweep (the divergent repo-wide duplication search,
        # lifted out of ``prompts/detail.md``'s audit section). Opt-in via a
        # dedicated ``foundational_invoker``. OFF by default — no production
        # caller wires it yet (pending objective measurement), so the default
        # ``detail`` path keeps its single authoring call; pass an invoker
        # explicitly (e.g. from an eval harness) to enable it. When on, the
        # result is handed into the authoring prompt as a block the model
        # *places* into the right section — it no longer searches.
        foundational_block = ""
        if foundational_invoker is not None:
            try:
                sweep = run_foundational_logic_sweep(
                    _render_step_sweep_context(step, scope_fence_block),
                    foundational_invoker,
                    run_logger=run_logger,
                    step_id=step.id,
                )
                foundational_block = format_foundational_logic_block(sweep)
            except Exception as exc:  # noqa: BLE001 — never sink detail on a sweep slip
                tool(f"foundational-logic sweep failed ({exc}); skipping")
        plan_references_block = extract_plan_references(plan_path)
        # Per-block prompt-budget breakdown collected during the render below
        # (reuses the formatter output; no second pass). Fed into the
        # invoke-time advisory (``_author_step_detail``) and the dry-run print.
        budget_blocks: list[tuple[str, int]] = []
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=repo_root,
            sibling_details=siblings,
            plan_references_block=plan_references_block,
            scope_fence_block=scope_fence_block,
            risk_context_block=render_declared_risk_context(plan),
            foundational_logic_block=foundational_block,
            # SPLIT arm only when a sweep invoker is wired; otherwise COMBINED
            # (legacy: inline grep directive + always-on self-check).
            split_mode=foundational_invoker is not None,
            # Folded members' full bodies for a merge re-author; empty (inert)
            # for every other call.
            prior_body=prior_body,
            # Pin the model to the canonical path so it doesn't author its
            # own (uncapped-slug) detail file under acceptEdits and strand
            # an orphan for the sweep.
            output_path=output_path,
            collect_blocks=budget_blocks,
            concept_tree=concept_tree,
            candidate_buckets=candidate_buckets,
            project_context=project_context,
            recovery_only=recovery_only,
        )

        if dry_run:
            # No work, no phase event — same rule as the already-exists
            # branch above. Dry-run only surfaces the rendered prompt to
            # the caller and never invokes claude. Print the budget breakdown
            # to stderr (at every level, ok included) for pre-spend inspection;
            # record no telemetry (nothing is sent).
            _print_detail_budget_breakdown(
                step,
                estimate_prompt_budget(
                    len(prompt.encode("utf-8")),
                    context_window=active_context_window(),
                    blocks=budget_blocks,
                ),
            )
            results.append(
                DetailResult(
                    step_id=step.id,
                    output_path=output_path,
                    written=False,
                    prompt=prompt,
                )
            )
            continue

        # ===== Per-step phase opens =====
        # Phase name embeds the step id so ``plan-tool runs show`` can
        # group rows without parsing a composite label. step_id /
        # step_title flow through as extras on phase_start so the JSONL
        # line still carries the structured fields.
        phase_name = f"detail-step-{step.id:02d}"
        phase_t0 = time.monotonic()
        phase_outcome = "success"
        phase_reason = ""
        phase_cached = False
        # Set when this step's in-loop apply returns BLOCKED-STRUCTURAL and the
        # escalated split is applied — suppresses the per-step lesson/result and
        # breaks the outer ``for step`` loop (ids renumbered out from under it).
        did_structural_split = False
        # Lesson capture requires a clean detail-quality converge (0 open
        # findings). Unaudited post-write capture is the closed defect.
        detail_quality_clean = False
        if run_logger is not None:
            run_logger.phase_start(
                phase_name,
                step_id=step.id,
                step_title=step.title,
            )
        try:
            # Resume check: did a prior run leave a valid checkpoint for this
            # exact step shape? Pre-scanned above into ``cached_by_id`` so
            # the [N/M] denominator is accurate from the start — re-reading
            # ``load_if_valid`` here would be wasted I/O against the same file.
            input_hash = _detail_step_input_hash(
                plan_path, step, project_context=project_context
            )
            ckpt_path = checkpoint_path(
                repo_root,
                plan_slug,
                _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
            )
            ckpt_name = _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
            cached: Optional[Checkpoint] = cached_by_id[step.id]
            # Resolve the resume confirm serially in the caller — the worker
            # never reads interactive stdin, so step 2 can dispatch it
            # off-thread. At the single-threaded path this is inline, exactly
            # as before, and its ``invoke_total`` fix-up stays cross-step.
            if cached is not None:
                try:
                    created_at = datetime.fromisoformat(cached.created_at)
                    age_seconds = (
                        datetime.now(timezone.utc) - created_at
                    ).total_seconds()
                except ValueError:
                    age_seconds = 0.0
                if not _confirm_resume(
                    prompt_fn,
                    step_id=step.id,
                    step_title=step.title,
                    checkpoint_age_seconds=age_seconds,
                ):
                    # User declined the resume — drop the cached body and
                    # fall through to the invoke loop. Discard is best-
                    # effort: a permissions/disk error here shouldn't abort
                    # the run we're explicitly trying to redo.
                    declined_path = _repo_relative(ckpt_path, repo_root)
                    try:
                        discard_checkpoint(ckpt_path)
                    except OSError as exc:
                        tool(
                            f"failed to discard declined "
                            f"checkpoint {ckpt_path} ({exc}); next run "
                            "may re-prompt against the same stale body"
                        )
                    else:
                        if run_logger is not None:
                            run_logger.checkpoint_discard(
                                ckpt_name,
                                "user_declined_resume",
                                step_id=step.id,
                                path=declined_path,
                            )
                    cached = None
                    # The pre-scan optimistically excluded this step from
                    # ``invoke_total`` (assumed resume). User declined, so
                    # bump the denominator back up so [N/M] stays accurate.
                    invoke_total += 1
            # Mirror the worker's resumed-body path for the run-log
            # ``phase_end`` and the scenario-capture gate below.
            phase_cached = cached is not None

            # Concurrency-safe authoring unit: resume-or-invoke → parse →
            # checkpoint → write. Returns the ``DetailResult`` inputs plus a
            # deferred ``(step_id, detail_rel)`` record — it never touches the
            # plan file. Step 2 dispatches this off-thread; here it runs inline
            # one step at a time, so behavior is byte-for-byte unchanged.
            outcome = _author_step_detail(
                step,
                prompt=prompt,
                output_path=output_path,
                cached=cached,
                input_hash=input_hash,
                ckpt_path=ckpt_path,
                ckpt_name=ckpt_name,
                plan_slug=plan_slug,
                phase_name=phase_name,
                invoke_idx=invoke_idx,
                invoke_total=invoke_total,
                reporter=reporter,
                run_logger=run_logger,
                invoker=invoker,
                repo_root=repo_root,
                plan_path=plan_path,
                capture_scenarios=capture_scenarios,
                arm=arm,
                foundational_invoker=foundational_invoker,
                budget_blocks=budget_blocks,
                plan=plan,
                candidate_buckets=candidate_buckets,
                require_deferral_envelope=require_deferral_envelope,
            )
            invoke_idx = outcome.invoke_idx
            handle = outcome.handle
            if not outcome.succeeded:
                # Parse or write failure: the worker already called
                # ``handle.fail`` and built the skip ``DetailResult``. Record
                # it and carry the phase outcome to the ``finally`` below.
                results.append(outcome.result)
                phase_outcome = outcome.phase_outcome
                phase_reason = outcome.phase_reason
                continue

            body = outcome.body
            elapsed = outcome.elapsed
            step_purity_findings = outcome.purity_findings
            _, detail_rel = outcome.update
            try:
                update_step_detail_field(plan_path, step.id, detail_rel)
            except DetailError as exc:
                handle.fail(elapsed, f"plan frontmatter update failed: {exc}")
                # File is on disk; plan update failed. Surface the partial
                # state explicitly so the user knows manual cleanup is
                # needed (delete the file, or hand-add the `detail:`
                # pointer to the step's frontmatter).
                results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=False,
                        skipped_reason=(
                            f"plan frontmatter update failed: {exc} "
                            f"(file written at {output_path}; manual cleanup "
                            "needed — delete it or add the `detail:` pointer "
                            "to the step manually)"
                        ),
                    )
                )
                phase_outcome = "error"
                phase_reason = f"frontmatter update failed: {exc}"
                continue

            # Sync the in-flight step with what we just persisted, so the
            # convergence loop's collect pass resolves the detail file
            # instead of short-circuiting on a stale ``step.detail is None``.
            step.detail = detail_rel

            # Surface the always-on purity self-check. A mixed step can't be
            # auto-fixed by re-authoring (the remedy is a refactor-then-
            # feature split), so this is a heads-up note, not a loop finding.
            # Fires regardless of --iterate; under --iterate the detail-
            # quality audit also re-detects it as a deferred finding.
            for pf in step_purity_findings:
                tool(f"mixed-step detected — {pf.body}", level="warning")
                mixed_steps.append((step.id, pf))

            # Detail file is on disk and the plan pointer is set. The
            # checkpoint was a "claude succeeded but the file isn't durable
            # yet" hedge — that state no longer exists, so drop it. Failures
            # here are non-fatal: a stale .json under .plan-tool/checkpoints/
            # will simply hit a hash-match on the next run and be
            # re-discarded.
            try:
                discard_checkpoint(ckpt_path)
            except OSError as exc:
                tool(
                    f"failed to discard checkpoint {ckpt_path} "
                    f"({exc}); next run may waste a hash-match read"
                )
            else:
                if run_logger is not None:
                    run_logger.checkpoint_discard(
                        ckpt_name,
                        "durable_write",
                        step_id=step.id,
                        path=_repo_relative(ckpt_path, repo_root),
                    )

            # New file is on disk *and* the plan frontmatter points at it
            # — any other ``NN-*.md`` siblings for this step id are now
            # definitively orphans (typically from a prior run whose slug
            # derivation differed because the step title was edited).
            # Sweep them into ``plan-details/<slug>/archive/`` so the
            # active directory stays clean. Best-effort; failures are
            # silent.
            archived = _archive_orphan_details(output_path, step.id)
            for dest in archived:
                tool(f"archived orphan detail to {dest}")

            handle.complete(elapsed, outcome.raw_bytes)

            # Record the scenario (re-runnable: plan path + step id + which arm
            # ran) for the prompt-mode A/B corpus — but only for an operator
            # ``plan-tool detail`` run (``capture_scenarios``, set by
            # ``cmd_detail``, NOT by bench / reconcile / the Phase-B self-call),
            # on a fresh + RELEVANT (categorized) authoring invoke. No-op unless
            # PLAN_TOOL_CAPTURE_SCENARIOS is also set.
            if capture_scenarios and not phase_cached:
                categories = categorize_scenario(
                    _detail_scenario_signals(step, plan)
                )
                capture_scenario(
                    "detail",
                    experiment=PROMPT_MODE_EXPERIMENT.name,
                    arm=arm_from_split(
                        arm, split=foundational_invoker is not None
                    ),
                    categories=categories,
                    inputs={
                        "plan": _repo_relative(plan_path, repo_root),
                        "step_id": step.id,
                        # Content hash pins an uncommitted plan edit at the same
                        # repo_sha so a replay can detect plan drift.
                        "plan_sha": content_sha(plan_path),
                    },
                    outcome={"written": True, "step_title": step.title},
                    repo_root=repo_root,
                    run_id=getattr(run_logger, "run_id", None),
                )

            convergence = _converge_run_grade_step_detail(
                step=step,
                plan=plan,
                plan_path=plan_path,
                repo_root=repo_root,
                plan_fingerprint=plan_fingerprint,
                plan_slug=plan_slug,
                invoker=invoker,
                reporter=reporter,
                run_logger=run_logger,
                budget=budget,
                allow_drift=allow_drift,
                auto_reconcile_on_drift=auto_reconcile_on_drift,
                collision_sidecar=collision_sidecar,
                triage=triage,
                include_info=include_info,
                allow_split=allow_split,
                prompt_fn=prompt_fn,
                structural_seen=structural_seen,
                project_context=project_context,
                recovery_only=recovery_only,
            )
            detail_quality_clean = convergence.detail_quality_clean
            did_structural_split = convergence.did_structural_split
            if convergence.structural_split_id is not None:
                structural_split_ids.add(convergence.structural_split_id)
            inloop_structural_recs.extend(
                convergence.structural_recommendations
            )

            # A retained apply may update the declaration that guides later
            # serial prompts. Keep the current attempt's prompt stable, then
            # make the next step read the accepted plan state from disk.
            if convergence.accepted_plan_edit and not did_structural_split:
                plan = parse_plan(plan_path)
                # An accepted apply this same iteration can retitle/re-scope
                # THIS step too (the class sweep apply-finding.md invites),
                # not only a later one — re-resolve so the lesson-capture
                # prompt and the per-step commit message below both read the
                # step that matches the ``plan`` object just refreshed,
                # rather than the pre-edit snapshot. This branch already
                # guards ``not did_structural_split``, so the step this
                # iteration is working on cannot have been renumbered away.
                step = plan.step_by_id(step.id)

            # Lesson capture only after a clean detail-quality converge —
            # never from an unaudited first write (BUG closed 2026-08-03).
            # No run_log instrumentation — step 4 deferred the "secondary
            # claude call inside a primary phase" pattern.
            _capture_detail_lessons_after_validation(
                extract_lessons=extract_lessons,
                body=body,
                did_structural_split=did_structural_split,
                validated=detail_quality_clean,
                plan=plan,
                plan_path=plan_path,
                step=step,
                repo_root=repo_root,
                lessons_invoker=lessons_invoker,
                reporter=reporter,
                strict_check=strict_check,
                run_logger=run_logger,
                equivalence_invoker=equivalence_invoker,
                detail_path=output_path,
            )

            if did_structural_split:
                # The original step's body was reverted and the step split away
                # — neither a "written" result nor a lesson applies to it. Record
                # why the phase ended without a body for the run log.
                phase_outcome = "structural-split"
                phase_reason = (
                    f"step {step.id} split into refactor + feature; "
                    "ids renumbered"
                )
            else:
                results.append(
                    DetailResult(
                        step_id=step.id,
                        output_path=output_path,
                        written=True,
                        deferrals=outcome.deferrals,
                    )
                )
                # Per-step commit (#122): commit this converged step now so an
                # interrupted batch keeps completed steps. Skip once any earlier
                # step failed leaving debris (e.g. an orphaned file from a
                # frontmatter-update failure) — per-step ``git add -A`` is only
                # safe while no prior step left the tree dirty. See docs/how-to/pipeline/detail.md.
                _prior_failure = any(
                    (not r.written)
                    and "already exists" not in (r.skipped_reason or "")
                    for r in results
                )
                if commit_step is not None and not _prior_failure:
                    commit_step(step.id, step.title)
        finally:
            # Emit phase_end on every exit (success continues, error
            # ``continue``s, and unexpected raises). ``cached`` lets
            # ``runs show`` render "0.0s (resumed)" without inspecting
            # the absence of ``claude_call_start`` events; ``reason``
            # carries the specific failure label when ``outcome`` is
            # not "success".
            if run_logger is not None:
                extra: dict[str, object] = {
                    "step_id": step.id,
                    "cached": phase_cached,
                }
                if phase_reason:
                    extra["reason"] = phase_reason
                run_logger.phase_end(
                    phase_name,
                    duration_ms=int((time.monotonic() - phase_t0) * 1000),
                    outcome=phase_outcome,
                    **extra,
                )

        # An in-loop split renumbered every id from ``step.id`` onward; the
        # remaining ``target_steps`` carry pre-split ids and must not be
        # processed. The ``finally`` above already emitted ``phase_end`` with
        # the ``structural-split`` outcome. The renumbered halves are
        # re-authored by the post-loop ``if structural_split_ids:`` block.
        if did_structural_split:
            break

    return _RunGradeDetailLifecycleResult(
        results=results,
        mixed_steps=mixed_steps,
        structural_split_ids=structural_split_ids,
        inloop_structural_recs=inloop_structural_recs,
    )


@spawn_cwd_from_repo_root
def generate_detail(
    plan_path: Path,
    *,
    repo_root: Path,
    step_id: Optional[int] = None,
    force: bool = False,
    dry_run: bool = False,
    invoker: DetailInvoker = shell_detail_invoker,
    reporter: Optional[ProgressReporter] = None,
    extract_lessons: bool = False,
    lessons_invoker: Optional[LessonsInvoker] = None,
    foundational_invoker: Optional[SweepInvoker] = None,
    capture_scenarios: bool = False,
    arm: Optional[str] = None,
    strict_check: bool = False,
    equivalence_invoker: Optional[EquivalenceInvoker] = None,
    resume: bool = True,
    prompt_fn: Optional[Callable[[str], str]] = None,
    yes: bool = False,
    run_logger: Optional[RunLogWriter] = None,
    budget: IterativeBudget = IterativeBudget(enabled=False),
    allow_drift: bool = False,
    auto_reconcile_on_drift: bool = True,
    collision_sidecar: bool = True,
    triage: bool = True,
    include_info: bool = False,
    allow_split: bool = False,
    jobs: int = 1,
    commit_step: Optional[Callable[[int, str], None]] = None,
    prior_body: str = "",
    recovery_only: bool = False,
) -> list[DetailResult]:
    """Author run-grade detail bodies and update their plan pointers.

    See ``DETAIL_FORMAT.md`` and ``docs/DETAIL_FLOW.md`` for the execution contract.
    """
    _reject_unmatched_plan_fence(plan_path)
    dispatch = _parse_detail_plan_and_dispatch(
        plan_path,
        repo_root=repo_root,
        step_id=step_id,
        force=force,
        dry_run=dry_run,
        invoker=invoker,
        reporter=reporter,
        extract_lessons=extract_lessons,
        resume=resume,
        prompt_fn=prompt_fn,
        run_logger=run_logger,
        budget=budget,
        allow_split=allow_split,
        jobs=jobs,
        commit_step=commit_step,
    )
    plan = dispatch.plan
    jobs = dispatch.jobs

    prepared = _prepare_run_grade_detail(
        plan_path,
        plan,
        repo_root=repo_root,
        step_id=step_id,
        force=force,
        dry_run=dry_run,
        reporter=reporter,
        resume=resume,
        prompt_fn=prompt_fn,
        run_logger=run_logger,
    )
    lifecycle = _run_grade_detail_lifecycle(
        prepared=prepared,
        plan_path=plan_path,
        repo_root=repo_root,
        force=force,
        dry_run=dry_run,
        invoker=invoker,
        extract_lessons=extract_lessons,
        lessons_invoker=lessons_invoker,
        foundational_invoker=foundational_invoker,
        capture_scenarios=capture_scenarios,
        arm=arm,
        strict_check=strict_check,
        equivalence_invoker=equivalence_invoker,
        budget=budget,
        allow_drift=allow_drift,
        auto_reconcile_on_drift=auto_reconcile_on_drift,
        collision_sidecar=collision_sidecar,
        triage=triage,
        include_info=include_info,
        allow_split=allow_split,
        jobs=jobs,
        commit_step=commit_step,
        prior_body=prior_body,
        recovery_only=recovery_only,
    )
    results = lifecycle.results
    mixed_steps = lifecycle.mixed_steps
    structural_split_ids = lifecycle.structural_split_ids
    inloop_structural_recs = lifecycle.inloop_structural_recs
    compute_plan_fingerprint = prepared.compute_plan_fingerprint
    concept_tree = prepared.concept_tree
    candidate_buckets = prepared.candidate_buckets
    reporter = prepared.reporter
    prompt_fn = prepared.prompt_fn
    run_logger = prepared.run_logger

    results = _handle_phase_b_splits(
        results,
        mixed_steps=mixed_steps,
        applied_in_loop_split_ids=structural_split_ids,
        context=_PhaseBSplitContext(
            plan_path=plan_path,
            repo_root=repo_root,
            invoker=invoker,
            reporter=reporter,
            extract_lessons=extract_lessons,
            lessons_invoker=lessons_invoker,
            foundational_invoker=foundational_invoker,
            strict_check=strict_check,
            equivalence_invoker=equivalence_invoker,
            prompt_fn=prompt_fn,
            run_logger=run_logger,
            budget=budget,
            allow_drift=allow_drift,
            auto_reconcile_on_drift=auto_reconcile_on_drift,
            collision_sidecar=collision_sidecar,
            triage=triage,
            include_info=include_info,
            allow_split=allow_split,
            plan_slug=_plan_slug(plan_path),
        ),
    )

    results = _handle_trigger_2_splits(
        results,
        structural_split_ids=structural_split_ids,
        inloop_structural_recs=inloop_structural_recs,
        context=_Trigger2SplitContext(
            plan_path=plan_path,
            repo_root=repo_root,
            invoker=invoker,
            reporter=reporter,
            extract_lessons=extract_lessons,
            lessons_invoker=lessons_invoker,
            foundational_invoker=foundational_invoker,
            strict_check=strict_check,
            equivalence_invoker=equivalence_invoker,
            prompt_fn=prompt_fn,
            run_logger=run_logger,
            budget=budget,
            allow_drift=allow_drift,
            auto_reconcile_on_drift=auto_reconcile_on_drift,
            collision_sidecar=collision_sidecar,
            triage=triage,
            include_info=include_info,
            plan_slug=_plan_slug(plan_path),
        ),
    )

    return _persist_final_detail_concepts(
        results,
        dry_run=dry_run,
        plan_path=plan_path,
        concept_tree=concept_tree,
        candidate_buckets=candidate_buckets,
        compute_plan_fingerprint=compute_plan_fingerprint,
    )


# --- private helpers -------------------------------------------------------


def _confirm_replace(
    prompt_fn: Callable[[str], str],
    *,
    step_id: int,
    step_title: str,
    output_path: Path,
) -> bool:
    """Ask whether to replace an existing detail file. Default skip.

    Non-TTY callers auto-decline so the historical "skip if exists"
    behavior is preserved for CI / piped contexts (where the default
    was idempotent skip). On a TTY the user sees the file path and
    can answer ``y`` to overwrite — the prior file is archived by
    ``_archive_existing_detail`` before the new body is written.
    """
    if not sys.stdin.isatty():
        return False
    # Step titles can be long multi-clause sentences with backticks; dumped
    # verbatim they wrap and the trailing ``[y/N]`` overwrites part of the
    # line. Collapse whitespace and cap to a short preview so the prompt
    # stays on one readable line — the file basename names the step
    # precisely if the preview is ambiguous.
    preview = " ".join(step_title.split())
    if len(preview) > 56:
        preview = preview[:55] + "…"
    raw = prompt_fn(
        f"Replace existing detail file for step {step_id} "
        f"({output_path.name})?\n  “{preview}”  [y/N] "
    ).strip().lower()
    return raw in {"y", "yes"}


def _confirm_resume(
    prompt_fn: Callable[[str], str],
    *,
    step_id: int,
    step_title: str,
    checkpoint_age_seconds: float,
) -> bool:
    """Ask the user whether to reuse a found checkpoint. Default yes.

    Non-TTY callers (CI, piped) auto-accept — they got here because
    ``resume=True`` and the input hash matched, and re-prompting in
    non-interactive contexts would deadlock on ``input()``. The age
    hint helps the user gauge staleness without having to ``stat``
    the checkpoint file with ``stat``.
    """
    if not sys.stdin.isatty():
        return True
    age_min = int(checkpoint_age_seconds // 60)
    raw = prompt_fn(
        f"Resume cached body for step {step_id} ({step_title!r}, "
        f"~{age_min}m old)? [Y/n] "
    ).strip().lower()
    if not raw:
        return True
    return raw in {"y", "yes"}


# --- Phase B: interactive refactor-then-feature split during authoring ----
#
# When the authoring purity self-check flags a mixed step, an interactive
# run can split it in place via create.py's proven ``_apply_step_split``
# primitive (renumbers to contiguous 1..N, rewires depends_on) and re-author
# both halves. The three helpers below are the pure, side-effect-scoped
# pieces that gate and support that flow; the orchestration wires them into
# ``generate_detail`` after the per-step loop.


# Leading zero-padded ``NN-`` id prefix on a detail filename. Swapped for the
# post-split id while preserving the slug exactly as it appears on disk (so a
# title edit that drifted the slug doesn't strand the rename).
_DETAIL_ID_PREFIX_RE = re.compile(r"^(\d+)-(.*)$")


def _detail_slug_key(detail_path: Path) -> str:
    """A detail file's identity *independent of its step id* — the filename
    with the leading ``NN-`` prefix stripped (``03-foo.md`` → ``foo.md``).

    Stable across a split's renumbering, which only rewrites the prefix. Lets
    the post-split results rebuild tell which restructured-region steps were
    actually authored *this run* (matched by slug key) from those merely
    renumbered and carried forward, rather than blanket-attributing writes.
    """
    m = _DETAIL_ID_PREFIX_RE.match(detail_path.name)
    return m.group(2) if m else detail_path.name


class _DetailMigration(NamedTuple):
    """One applied downstream repoint plus what undoes it.

    ``src``/``dst`` are ``None`` when only the pointer moved (no file was on
    disk to rename), so the rollback restores the pointer without a move.
    """

    step: "Step"
    previous_detail: Optional[str]
    src: Optional[Path]
    dst: Optional[Path]


def _migrate_downstream_details_after_split(
    new_steps: "list[Step]",
    *,
    repo_root: Path,
    target_id: int,
    shift: int,
) -> "list[_DetailMigration]":
    """Rename downstream detail files to their post-split ids and repoint
    ``step.detail``, mutating ``new_steps`` in place.

    Returns the applied migrations in order, so a caller whose subsequent plan
    write fails can undo them via :func:`_rollback_detail_migration` —
    :func:`_migrate_and_write_split` is the pairing that owns that.

    ``_apply_step_split`` renumbers every step after the target by ``shift``
    (= ``len(replacements) - 1``) but leaves their ``detail`` pointer — a
    path string carrying the *old* ``NN-`` prefix (``03-foo.md``) —
    untouched. Left alone the stale prefix breaks the idempotent skip rule:
    ``derive_detail_path`` would compute ``04-foo.md``, find nothing, and
    re-author an already-written step. So each downstream step's file is
    renamed ``{old:02d}`` → ``{new:02d}`` (slug preserved verbatim from the
    on-disk name) and its pointer updated to match.

    Renames run high→low id so a step never clobbers the file of the next
    one up. Best-effort per step: a missing/odd-named source file just
    repoints the pointer without a move. The split target's own (now-stale)
    file is left for the orphan sweep when its refactor half is re-authored.
    """
    # Downstream = new ids above the last replacement (target_id + shift).
    # High→low avoids a rename clobbering the next step's not-yet-moved file.
    downstream = sorted(
        (s for s in new_steps if s.id > target_id + shift and s.detail),
        key=lambda s: s.id,
        reverse=True,
    )
    journal: "list[_DetailMigration]" = []
    for step in downstream:
        old_path = repo_root / step.detail
        m = _DETAIL_ID_PREFIX_RE.match(old_path.name)
        if not m:
            continue  # no NN- prefix to swap; leave the pointer as-is
        new_path = old_path.with_name(f"{step.id:02d}-{m.group(2)}")
        previous_detail = step.detail
        renamed = False
        if old_path != new_path and old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            # ``rename`` silently overwrites its destination, so a stray file
            # already sitting at the target prefix (e.g. an orphan from a
            # prior run) would be clobbered. Archive it first — best-effort,
            # mirroring the overwrite-time archival in the main write path.
            if new_path.exists():
                _archive_existing_detail(new_path)
            old_path.rename(new_path)
            renamed = True
        step.detail = _repo_relative(new_path, repo_root)
        # ``or renamed`` is defensive, not live: a rename implies a changed
        # pointer, so the first clause already covers it.
        if step.detail != previous_detail or renamed:
            journal.append(
                _DetailMigration(
                    step,
                    previous_detail,
                    old_path if renamed else None,
                    new_path if renamed else None,
                )
            )
    return journal


def _rollback_detail_migration(journal: "list[_DetailMigration]") -> None:
    """Undo an applied downstream migration LIFO.

    Best-effort per entry, mirroring ``scope_out._rollback``: one failed undo
    must not abort the rest, since the caller re-raises the original error. A
    pointer is restored only when its file made it back, so the two never
    disagree. A collision victim the migration archived stays archived — it was
    an orphan, and the copy survives under ``archive/``.
    """
    for entry in reversed(journal):
        restored = True
        if entry.src is not None and entry.dst is not None:
            try:
                if entry.dst.exists() and not entry.src.exists():
                    entry.src.parent.mkdir(parents=True, exist_ok=True)
                    entry.dst.rename(entry.src)
            except OSError:
                pass
            # Keyed on where the file actually is, not on whether the move
            # raised — a vanished source is as un-restored as a failed rename.
            restored = entry.src.exists()
        if restored:
            entry.step.detail = entry.previous_detail


def _migrate_and_write_split(
    plan_path: Path,
    plan: "Plan",
    new_steps: "list[Step]",
    *,
    repo_root: Path,
    target_id: int,
    shift: int,
) -> None:
    """Migrate downstream details, then persist the split plan — all-or-nothing.

    The renames must land *first* (the write persists the repointed ``detail:``
    values the migration produces), so a failed write has to undo them or every
    downstream pointer dangles at a file that moved. ``write_plan`` can refuse
    for two ordinary reasons — its compare-and-swap on a concurrent edit, and
    its re-validation of the folded plan — and both callers reach it across a
    long window (a Claude proposal plus an operator confirm). Journal +
    rollback, mirroring ``scope_out.apply_narrow``.
    """
    journal = _migrate_downstream_details_after_split(
        new_steps, repo_root=repo_root, target_id=target_id, shift=shift
    )
    try:
        write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))
    except Exception:
        _rollback_detail_migration(journal)
        raise


def _confirm_split(
    prompt_fn: Callable[[str], str],
    *,
    step: Step,
    replacements: "list[Step]",
) -> bool:
    """Ask whether to split a mixed step into the proposed refactor +
    feature pair. Default NO — a structural plan edit shouldn't happen
    without explicit assent. Non-TTY callers auto-decline (the mixed-step
    finding still surfaces as a warning; only the auto-split is skipped)."""
    if not sys.stdin.isatty():
        return False
    lines = [
        f"Step {step.id} ({step.title!r}) looks mixed (refactor + feature).",
        "Proposed split:",
    ]
    for rep in replacements:
        ct = rep.change_type.value if rep.change_type else "?"
        lines.append(f"  → {rep.title} [{ct}]")
    lines.append("Apply this split and re-author both halves? [y/N] ")
    raw = prompt_fn("\n".join(lines) + " ").strip().lower()
    return raw in {"y", "yes"}


@dataclass(frozen=True)
class SplitResult:
    """Outcome of an on-demand :func:`split_step` run.

    ``new_ids`` / ``new_titles`` describe the replacement steps spliced in
    place of ``target_id`` (post-renumber, contiguous). ``detail_results``
    is the per-half authoring outcome — empty when the caller passed
    ``author_details=False`` or ``dry_run=True``.

    ``renumber`` is the ``(old_id, new_id)`` map for every step and
    ``new_plan`` the post-split ``(id, title, depends_on)`` rows — both
    populated for a preview (``dry_run=True``) so a caller can show what the
    split *would* do without any disk mutation; left empty on a real run.
    """

    target_id: int
    original_title: str
    new_ids: list[int]
    new_titles: list[str]
    detail_results: list[DetailResult]
    dry_run: bool = False
    renumber: list[tuple[int, int]] = field(default_factory=list)
    new_plan: list[tuple[int, str, list[int]]] = field(default_factory=list)


def split_step(
    plan_path: Path,
    *,
    target_id: int,
    new_titles: list[str],
    repo_root: Path,
    author_details: bool = True,
    dry_run: bool = False,
    invoker: DetailInvoker = shell_detail_invoker,
    reporter: Optional[ProgressReporter] = None,
    run_logger: Optional[RunLogWriter] = None,
    prompt_fn: Optional[Callable[[str], str]] = None,
    budget: IterativeBudget = IterativeBudget(enabled=False),
) -> SplitResult:
    """Split step ``target_id`` into ``new_titles`` sub-steps on demand.

    The deterministic, operator-driven counterpart to ``detail --split``'s
    reactive Claude-proposed refactor+feature pass: the caller names the
    replacement steps explicitly — typically to resolve a completeness
    ``BLOCKED`` finding that calls for a step ``apply_finding`` can't create.
    Reuses the same primitives the Phase-B split path does:
    :func:`plan_tool.create._apply_step_split` renumbers to a contiguous
    ``1..N`` and rewires ``depends_on`` (each half chained after the prior,
    the first inheriting the target's edges), then
    :func:`_migrate_downstream_details_after_split` renames downstream detail
    files to their new ids. Each new (detail-less) half is then authored
    unless ``author_details`` is False.

    ``dry_run=True`` validates and computes the renumber/new-plan preview on
    the :class:`SplitResult` but performs no disk mutation (no plan write, no
    file renames, no authoring).

    Halves inherit the target's ``change_type`` / ``complexity`` / ``concept_ids``
    but never its ``intent`` — the target's why described the whole step, and
    copying it onto both halves would make it authoritative and wrong on both.

    Raises :class:`DetailError` when the step is missing, fewer than two
    distinct non-empty titles are given, the plan isn't canonically numbered
    (contiguous ``1..N`` in order — the renumber + downstream-migration
    primitives assume step id equals position, which only holds for the
    canonical numbering the tool itself produces), or the split is unsafe (a
    step at or after the target is ``done`` — renumbering it would orphan its
    id-keyed run state; a ``current``/``pending`` step splits cleanly).
    """
    from plan_tool.create import (  # lazy: avoid create↔detail import cycle
        CreateError,
        _apply_step_split,
    )

    titles = [t.strip() for t in new_titles if t.strip()]
    if len(titles) < 2:
        raise DetailError(
            f"split needs at least two replacement titles (got {len(titles)})"
        )
    # Reject duplicate replacement titles (case-insensitive): two sub-steps
    # with the same title are always a mistake — they'd produce semantically
    # identical steps the completeness audit then has to flag.
    lowered = [t.lower() for t in titles]
    dupes = sorted({t for t, lo in zip(titles, lowered) if lowered.count(lo) > 1})
    if dupes:
        raise DetailError(
            "split replacement titles must be distinct; duplicated: "
            + ", ".join(repr(d) for d in dupes)
        )

    plan = parse_plan(plan_path)
    # The renumber + downstream-migration primitives equate step id with
    # 1-based position. That holds for every plan the tool produces (create
    # and each split renumber to contiguous 1..N in order), but the schema
    # permits gaps/out-of-order ids through direct editing; on such a plan the
    # id-keyed migration would silently strand detail files. Refuse rather
    # than corrupt — `plan-tool validate`/re-plan can restore canonical ids.
    expected = list(range(1, len(plan.steps) + 1))
    if [s.id for s in plan.steps] != expected:
        raise DetailError(
            f"cannot split {plan_path.name}: step ids are not canonical "
            f"(expected contiguous {expected[0]}..{expected[-1]} in order). "
            "Restore canonical numbering (re-plan) before splitting."
        )
    pos = next(
        (i for i, s in enumerate(plan.steps) if s.id == target_id), None
    )
    if pos is None:
        raise DetailError(f"step {target_id} not found in {plan_path.name}")
    target = plan.steps[pos]

    safe, blocking = split_is_safe(plan, target_id)
    if not safe:
        # ``blocking`` is every DONE step at-or-after the target — it may
        # include the target itself, so don't label them all "downstream".
        raise DetailError(
            f"cannot split step {target_id}: step(s) {blocking} are done, so "
            "renumbering would orphan their run state — restructure via "
            "re-plan instead"
        )

    # Replacement steps inherit the parent's change_type/complexity; intent
    # is deliberately not inherited (the target's why described the whole
    # step). id, depends_on, and status are placeholders that
    # ``_apply_step_split`` overwrites deterministically (the first half
    # inherits the target's status, later halves pending). ``detail=None``
    # so each half is authored fresh below.
    replacements = [
        Step(
            id=0,
            title=t,
            change_type=target.change_type,
            complexity=target.complexity,
            concept_ids=list(target.concept_ids),
        )
        for t in titles
    ]
    try:
        new_steps = _apply_step_split(plan.steps, target_id, replacements)
    except CreateError as exc:
        raise DetailError(f"split failed: {exc}") from exc

    # Replacements occupy positions ``pos .. pos+shift`` → contiguous ids
    # ``pos+1 .. pos+1+shift`` after the renumber.
    shift = len(replacements) - 1
    new_ids = list(range(pos + 1, pos + 1 + len(replacements)))

    if dry_run:
        # Preview only: the old→new id map and the post-split rows. No write,
        # no rename, no authoring.
        return SplitResult(
            target_id=target_id,
            original_title=target.title,
            new_ids=new_ids,
            new_titles=titles,
            detail_results=[],
            dry_run=True,
            renumber=_split_renumber_map(plan.steps, target_id, len(replacements)),
            new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps],
        )

    _migrate_and_write_split(
        plan_path,
        plan,
        new_steps,
        repo_root=repo_root,
        target_id=target_id,
        shift=shift,
    )

    # Best-effort step-provenance telemetry (#238 plan-mass "audit-induced
    # growth"): record the new halves' titles so a later completeness report
    # can tell them apart from steps the plan's author wrote. Never lets a
    # telemetry failure perturb the split, which has already landed on disk.
    try:
        from plan_tool.review_persistence import compute_plan_fingerprint
        from plan_tool.telemetry import record_step_provenance

        record_step_provenance(
            repo_root,
            plan_slug=_plan_slug(plan_path),
            new_step_titles=titles,
            mechanism="split",
            plan_fingerprint=compute_plan_fingerprint(plan_path),
        )
    except Exception:
        pass

    detail_results: list[DetailResult] = []
    if author_details:
        for hid in new_ids:
            detail_results.extend(
                generate_detail(
                    plan_path,
                    repo_root=repo_root,
                    step_id=hid,
                    force=False,
                    invoker=invoker,
                    reporter=reporter,
                    resume=False,
                    prompt_fn=prompt_fn,
                    run_logger=run_logger,
                    budget=budget,
                    allow_split=False,
                )
            )
    return SplitResult(
        target_id=target_id,
        original_title=target.title,
        new_ids=new_ids,
        new_titles=titles,
        detail_results=detail_results,
    )


def _split_renumber_map(
    old_steps: "list[Step]", target_id: int, n_replacements: int
) -> "list[tuple[int, int]]":
    """``(old_id, new_id)`` for every pre-split step after a split of
    ``target_id`` into ``n_replacements`` sub-steps.

    Mirrors :func:`plan_tool.create._apply_step_split`'s positional renumber
    on a *canonical* plan (id == position): steps before the target keep
    their id; the target folds into the terminal replacement id
    (``target_id + n_replacements - 1``); steps after shift by
    ``n_replacements - 1``. Preview-only — the real renumber is done by
    ``_apply_step_split``.
    """
    shift = n_replacements - 1
    out: list[tuple[int, int]] = []
    for s in old_steps:
        if s.id < target_id:
            out.append((s.id, s.id))
        elif s.id == target_id:
            out.append((s.id, target_id + shift))
        else:
            out.append((s.id, s.id + shift))
    return out


# --- Merge cluster: the structural inverse of the split cluster above -------
#
# ``merge_steps`` folds a contiguous, not-yet-done (no ``DONE`` member or
# downstream step) run of steps into one and
# re-authors a single coherent detail file. It reuses create.py's pure
# ``_apply_step_merge`` transform exactly as ``split_step`` reuses
# ``_apply_step_split``, but every index axis inverts: downstream ids shift
# *down* by ``len(set) - 1``, the downstream migration processes *low→high*,
# and detail handling is *combine-then-re-author* (full member bodies fed
# through the ``${prior_body_block}`` seam), not *create*. The four siblings
# below mirror ``split_safety.split_is_safe`` / ``_migrate_downstream_details_after_split``
# / ``_confirm_split`` / ``SplitResult`` shape-for-shape.


def _merge_is_safe(plan: Plan, merge_ids: "list[int]") -> "tuple[bool, list[int]]":
    """Whether ``merge_ids`` can be folded without orphaning run state.

    A merge rewrites the folded members **and** renumbers every step after
    the merged region (shifting ids down by ``len(set) - 1`` and renaming
    their detail files via :func:`_migrate_downstream_details_after_merge`).
    The only durable, id-keyed run state a renumber orphans is a ``DONE``
    step's (``step N green`` commit subject, completion status). So a ``DONE``
    *member* blocks (it has run), and so does a ``DONE`` step *after* the
    region: renumbering/renaming it would orphan that state — the exact
    hazard :func:`~plan_tool.split_safety.split_is_safe` guards with
    ``s.id >= target_id``, applied to the post-region steps a merge likewise
    renumbers. Everything else folds/renumbers cleanly, **including a
    ``CURRENT`` step**: ``current`` means "next runnable" after
    ``create``/``detail`` authoring, not "mid-execution" (a ``CURRENT`` step
    never has a green commit — green ⟹ ``DONE``), so a freshly-authored plan
    can merge its current step; the survivor then inherits ``current`` (see
    :func:`~plan_tool.create._apply_step_merge`). A step *before* the region
    (``id < max(merge_ids)``, non-member) never renumbers, so it never blocks.
    A parked (``scope: deferred``/``wont_do``) step is still ``PENDING`` and
    carries no run state, so it is run-state-safe here (the separate
    scope-commitment gate lives in ``merge_steps``'s assembly).

    Accepted residual risk (same as :func:`~plan_tool.split_safety.split_is_safe`):
    the ``_persist_step_completion`` SIGKILL window (``launcher.py``) can leave a
    ``CURRENT`` member/downstream step with a landed ``step N:`` lesson but no
    ``DONE`` flip; folding/renumbering it then orphans that lesson's step
    reference. The window is narrow and the fallout soft (advisory prior-step
    context), so this gate does **not** re-add a run-log/lesson "run evidence"
    scan to catch it — that signal proved unsound (written by detail/create too,
    keyed to pre-renumber ids, TTL-evictable); ``DONE`` is the only durable
    renumber-orphanable signal.

    Returns ``(safe, blocking_ids)`` so the caller can name what blocked.
    """
    members = set(merge_ids)
    region_max = max(merge_ids)
    blocking = sorted(
        s.id
        for s in plan.steps
        if (s.id in members or s.id > region_max)
        and s.status == StepStatus.DONE
    )
    return (not blocking, blocking)


def _migrate_downstream_details_after_merge(
    new_steps: "list[Step]",
    *,
    repo_root: Path,
    merged_new_id: int,
) -> None:
    """Rename downstream detail files to their post-merge ids and repoint
    ``step.detail``, mutating ``new_steps`` in place.

    The inverse of :func:`_migrate_downstream_details_after_split`: a merge
    shifts every post-region step's id *down*, so the on-disk ``NN-`` prefix
    is stale-high and must be swapped to the new (lower) id. Reuses
    :data:`_DETAIL_ID_PREFIX_RE` to swap the prefix while preserving each
    file's slug exactly as it appears on disk.

    Renames run **low→high** id (split runs high→low): because ids *decrease*,
    the lowest downstream step renames first — into the slot freshly vacated
    by the fold — so a rename never clobbers a not-yet-moved lower step's
    file. Best-effort per step: a missing but ``NN-``-prefixed source file
    repoints the pointer without a move; an odd-named source leaves the
    pointer unchanged. ``merged_new_id`` is the survivor id (= ``lo``); the
    merged step at that id is excluded by ``>`` and pre-region steps never
    renumber, so neither is touched here.
    """
    # Downstream = steps strictly above the survivor id. Low→high so a rename
    # never clobbers the next (lower) step's not-yet-moved file.
    downstream = sorted(
        (s for s in new_steps if s.id > merged_new_id and s.detail),
        key=lambda s: s.id,
    )
    for step in downstream:
        old_path = repo_root / step.detail
        m = _DETAIL_ID_PREFIX_RE.match(old_path.name)
        if not m:
            continue  # no NN- prefix to swap; leave the pointer as-is
        new_path = old_path.with_name(f"{step.id:02d}-{m.group(2)}")
        if old_path != new_path and old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            # ``rename`` silently overwrites; archive any stray file already at
            # the destination first (mirroring split's overwrite-time guard).
            if new_path.exists():
                _archive_existing_detail(new_path)
            old_path.rename(new_path)
        step.detail = _repo_relative(new_path, repo_root)


def _confirm_merge(
    prompt_fn: Callable[[str], str],
    *,
    steps_to_merge: "list[Step]",
    merged_title: str,
) -> bool:
    """Ask whether to fold ``steps_to_merge`` into one re-authored step.

    Mirrors :func:`_confirm_split`: default NO — a structural plan edit
    shouldn't happen without explicit assent; non-TTY callers auto-decline
    (the merge never runs unattended). Defined here beside ``_confirm_split``
    but invoked by step 3's ``cmd_merge`` (the CLI owns the TTY gate);
    ``merge_steps`` itself never prompts.
    """
    if not sys.stdin.isatty():
        return False
    lines = ["Merging:"]
    for s in steps_to_merge:
        lines.append(f"  → {s.id}. {s.title}")
    lines.append(f"into one step: {merged_title!r}")
    lines.append("Apply this merge and re-author the combined detail? [y/N] ")
    raw = prompt_fn("\n".join(lines) + " ").strip().lower()
    return raw in {"y", "yes"}


@dataclass(frozen=True)
class MergeResult:
    """Outcome of a :func:`merge_steps` run.

    ``folded_ids`` / ``folded_titles`` describe the *input* set folded away
    (the merge analogue of :class:`SplitResult`'s ``new_ids`` / ``new_titles``
    output set). ``merged_id`` / ``merged_title`` name the single survivor
    (post-renumber, ``= min(merge_ids)``). ``detail_results`` is the merged
    re-author's outcome — empty when ``author_details=False`` or
    ``dry_run=True``.

    ``renumber`` (``(old_id, new_id)`` for every step) and ``new_plan``
    (post-merge ``(id, title, depends_on)`` rows) are populated **only** on a
    preview (``dry_run=True``) so a caller can show what the merge *would* do
    without any disk mutation; both are empty on a real run.
    """

    merged_id: int
    merged_title: str
    folded_ids: list[int]
    folded_titles: list[str]
    detail_results: list[DetailResult]
    dry_run: bool = False
    renumber: list[tuple[int, int]] = field(default_factory=list)
    new_plan: list[tuple[int, str, list[int]]] = field(default_factory=list)


# Dominant-type / -complexity precedence for the folded set (higher wins).
_MERGE_CHANGE_TYPE_RANK = {
    ChangeType.NON_CODE: 0,
    ChangeType.REFACTOR: 1,
    ChangeType.FEATURE: 2,
}
_MERGE_COMPLEXITY_RANK = {
    Complexity.LOW: 0,
    Complexity.MEDIUM: 1,
    Complexity.HIGH: 2,
}


def _unanimous_intent(member_steps: list[Step]) -> Optional[str]:
    """Keep a shared intent only when every member states the same usable value.

    Usable = survives the fence presence set (``None`` / blank / any of the six
    TODO/TBD spellings :func:`is_placeholder_intent` owns). Compare after
    :func:`collapse_intent_to_one_line`; return the first member's text as
    written (collapse is comparison-only). Prefer absent over a half-true why.
    """
    usable: list[str] = []
    for step in member_steps:
        intent = step.intent
        if intent is None:
            return None
        collapsed = collapse_intent_to_one_line(intent)
        # Same omit predicate as ``_render_intent_section`` (fence presence).
        if not collapsed or is_placeholder_intent(collapsed):
            return None
        usable.append(intent)
    keys = {collapse_intent_to_one_line(v) for v in usable}
    if len(keys) != 1:
        return None
    return usable[0]


def merge_steps(
    plan_path: Path,
    *,
    merge_ids: list[int],
    title: Optional[str] = None,
    repo_root: Path,
    author_details: bool = True,
    dry_run: bool = False,
    invoker: DetailInvoker = shell_detail_invoker,
    reporter: Optional[ProgressReporter] = None,
    run_logger: Optional[RunLogWriter] = None,
    prompt_fn: Optional[Callable[[str], str]] = None,
    budget: IterativeBudget = IterativeBudget(enabled=False),
) -> MergeResult:
    """Fold a contiguous not-yet-done run of steps into one re-authored step.

    "Not-yet-done" = no ``DONE`` member or downstream step (a ``CURRENT`` member
    is allowed; the survivor inherits its ``current`` status). The structural
    inverse of :func:`split_step`: reuses
    :func:`plan_tool.create._apply_step_merge` to collapse ``merge_ids`` to a
    single survivor at ``min(merge_ids)``, renumber survivors to contiguous
    ``1..N`` (downstream ids shift *down* by ``len(set) - 1``), then
    :func:`_migrate_downstream_details_after_merge` renames downstream detail
    files to their new (lower) ids. The merged step is re-authored from the
    folded members' **full** detail bodies (fed through the
    ``${prior_body_block}`` seam, untruncated) and the folded-away files are
    archived.

    The survivor keeps an ``intent`` only when every folded member states the
    same usable value (fence presence set; compare after whitespace collapse);
    otherwise the field clears. Prefer absent over a half-true why. Does not
    touch ``Plan.intent``.

    ``dry_run=True`` validates and computes the renumber / new-plan preview on
    the :class:`MergeResult` but performs no disk mutation. ``merge_steps``
    never prompts — step 3's ``cmd_merge`` owns the TTY confirmation gate via
    :func:`_confirm_merge` before it calls here.

    Raises :class:`DetailError` (before any disk mutation) for fewer than two
    distinct ids, non-canonical numbering, an unknown id, an unsafe
    (run-started) set, a mixed-``scope`` set, or an invalid graph surfaced by
    ``_apply_step_merge``.
    """
    from plan_tool.create import (  # lazy: avoid create↔detail import cycle
        CreateError,
        _apply_step_merge,
    )

    members = set(merge_ids)
    if len(members) < 2:
        raise DetailError(
            f"merge needs at least two distinct step ids (got {len(members)})"
        )

    plan = parse_plan(plan_path)
    # The renumber + downstream-migration primitives equate step id with
    # 1-based position; refuse a non-canonical plan rather than strand detail
    # files (same guard/wording as ``split_step``).
    expected = list(range(1, len(plan.steps) + 1))
    if [s.id for s in plan.steps] != expected:
        raise DetailError(
            f"cannot merge {plan_path.name}: step ids are not canonical "
            f"(expected contiguous {expected[0]}..{expected[-1]} in order). "
            "Restore canonical numbering (re-plan) before merging."
        )
    by_id = {s.id: s for s in plan.steps}
    unknown = sorted(i for i in members if i not in by_id)
    if unknown:
        raise DetailError(
            f"cannot merge: step(s) {unknown} not found in {plan_path.name}"
        )

    safe, blocking = _merge_is_safe(plan, merge_ids)
    if not safe:
        raise DetailError(
            f"cannot merge step(s) {blocking}: are done — "
            "restructure via re-plan instead"
        )

    member_steps = [by_id[i] for i in sorted(members)]

    # Scope-commitment gate (separate from the run-state safety gate above): a
    # parked member is run-state-safe yet still rejected when the set mixes
    # scopes. Folding a parked member into a committed step would resurrect
    # abandoned work into runnable selection; the inverse would abandon
    # committed work. With a uniform set the merged step inherits that scope.
    scopes = {s.scope for s in member_steps}
    if len(scopes) > 1:
        raise DetailError(
            "cannot merge a mixed-scope set: members carry "
            f"{sorted(sc.value for sc in scopes)} — require a uniform scope "
            "(promote/park members first)"
        )
    merged_scope = next(iter(scopes))

    # Assemble the authored fields for the merged Step. As with ``split_step``
    # replacements, the shared transform owns structural fields: id,
    # depends_on, status, and the ordered union of member concept ownership.
    # Leave ``concept_ids`` at its default; placeholder ownership is never the
    # source of truth for a fold.
    merged_title = title.strip() if title and title.strip() else member_steps[0].title

    def _dedup(seq: "list[str]") -> "list[str]":
        return list(dict.fromkeys(seq))

    merged_files = _dedup([f for s in member_steps for f in s.files])
    merged_creates = _dedup([c for s in member_steps for c in s.creates])

    typed = [s.change_type for s in member_steps if s.change_type is not None]
    merged_change_type = (
        max(typed, key=lambda ct: _MERGE_CHANGE_TYPE_RANK[ct]) if typed else None
    )
    cplx = [s.complexity for s in member_steps if s.complexity is not None]
    merged_complexity = (
        max(cplx, key=lambda c: _MERGE_COMPLEXITY_RANK[c]) if cplx else None
    )

    merged_features = _dedup([f for s in member_steps for f in s.features])
    merged_allowed = _dedup([m for s in member_steps for m in s.allowed_mentions])
    merged_gate = _dedup([g for s in member_steps for g in s.gate])
    # ``enforce_test_authoring``: True if any member forces it on; else preserve
    # an explicit False; else None (inherit the plan default).
    eta_values = [s.enforce_test_authoring for s in member_steps]
    if any(v is True for v in eta_values):
        merged_eta: Optional[bool] = True
    elif any(v is False for v in eta_values):
        merged_eta = False
    else:
        merged_eta = None

    merged = Step(
        id=0,
        title=merged_title,
        files=merged_files,
        creates=merged_creates,
        allowed_mentions=merged_allowed,
        features=merged_features,
        complexity=merged_complexity,
        change_type=merged_change_type,
        enforce_test_authoring=merged_eta,
        gate=merged_gate,
        depends_on=[],
        detail=None,
        scope=merged_scope,
        intent=_unanimous_intent(member_steps),
    )

    try:
        new_steps = _apply_step_merge(plan.steps, merge_ids, merged)
    except CreateError as exc:
        raise DetailError(f"merge failed: {exc}") from exc

    lo = min(members)
    eliminated = len(members) - 1
    merged_new_id = lo  # the contiguous-set fold puts the survivor at ``lo``
    folded_ids = sorted(members)
    folded_titles = [s.title for s in member_steps]

    if dry_run:
        # Preview only: restate ``_apply_step_merge``'s renumber arithmetic on
        # a canonical plan. No write, no rename, no authoring.
        def _old_to_new(old_id: int) -> int:
            if old_id < lo:
                return old_id
            if old_id in members:
                return merged_new_id
            return old_id - eliminated

        renumber = [(s.id, _old_to_new(s.id)) for s in plan.steps]
        return MergeResult(
            merged_id=merged_new_id,
            merged_title=merged_title,
            folded_ids=folded_ids,
            folded_titles=folded_titles,
            detail_results=[],
            dry_run=True,
            renumber=renumber,
            new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps],
        )

    # Real run. No confirmation here — step 3's ``cmd_merge`` owns the TTY
    # gate before calling. Order: snapshot+read folded bodies → migrate
    # downstream → write plan → re-author merged → archive folded files.

    # 1. Snapshot the folded members' detail paths and read their FULL bodies
    #    (the combine input). Tolerates undetailed members — a merge needs only
    #    a not-yet-done set, and a PENDING/CURRENT member may carry no detail yet.
    folded_paths: list[Path] = []
    prior_bodies: list[str] = []
    for s in member_steps:
        if not s.detail:
            continue
        p = repo_root / s.detail
        folded_paths.append(p)
        if p.is_file():
            body = p.read_text(encoding="utf-8", errors="replace")
            require_supported_detail_format_version(body, path=p)
            prior_bodies.append(strip_detail_format_version_marker(body))
    prior_body = "\n\n".join(prior_bodies)

    # 2. Rename downstream detail files down to their new ids.
    _migrate_downstream_details_after_merge(
        new_steps, repo_root=repo_root, merged_new_id=merged_new_id
    )
    # 3. Persist the renumbered plan.
    write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))

    # 4. Re-author the merged half from the combined full bodies. ``force``
    #    regenerates through the seven-section gate; ``allow_split=False``
    #    prevents re-splitting the just-merged step; ``prior_body`` carries the
    #    full member bodies untruncated via ``${prior_body_block}``.
    detail_results: list[DetailResult] = []
    if author_details:
        detail_results = generate_detail(
            plan_path,
            repo_root=repo_root,
            step_id=merged_new_id,
            force=True,
            invoker=invoker,
            reporter=reporter,
            resume=False,
            prompt_fn=prompt_fn,
            run_logger=run_logger,
            budget=budget,
            allow_split=False,
            extract_lessons=False,
            prior_body=prior_body,
        )

    # 5. Archive the folded-away files (best-effort) after the re-author. Skip
    #    the merged step's own current file (overwritten in place when its slug
    #    coincided with a member's).
    merged_after = next((s for s in parse_plan(plan_path).steps if s.id == merged_new_id), None)
    merged_detail_path = (
        repo_root / merged_after.detail
        if merged_after is not None and merged_after.detail
        else None
    )
    for p in folded_paths:
        if p.exists() and p != merged_detail_path:
            _archive_existing_detail(p)

    merged_title_final = merged_after.title if merged_after is not None else merged_title
    return MergeResult(
        merged_id=merged_new_id,
        merged_title=merged_title_final,
        folded_ids=folded_ids,
        folded_titles=folded_titles,
        detail_results=detail_results,
    )


@dataclass(frozen=True)
class MergeBridgeResult:
    """Disposition of one :func:`merge_bridge` call — the merge analog of
    :class:`plan_tool.reground.RegroundResult` /
    :class:`plan_tool.scope_out.ScopeOutResult` /
    :class:`plan_tool.launcher.EscalateResult`.

    ``outcome`` is exactly one of four strings; only ``"applied"`` mutates:
      - ``"applied"`` — the merge was confirmed and :func:`merge_steps` folded
        the set; ``merge_result`` is that real run's :class:`MergeResult`. If
        re-authoring the merged step failed *after* the fold persisted,
        ``merge_result`` is ``None`` and ``apply_error`` carries the failure —
        the plan is folded-but-unauthored (complete it with ``plan-tool
        detail``); the outcome stays ``"applied"`` because the structural fold
        (which renumbers step ids) did land and callers must treat it as such.
      - ``"recommended"`` — the merge is valid and safe but not actuated
        (``allow_merge=False`` or a declined / non-TTY confirm); ``merge_result``
        is the dry-run preview so a caller can render what the merge *would* do.
      - ``"unsafe"`` — a member or downstream step is ``DONE`` (its id-keyed
        run state would be orphaned by the renumber); ``blocking_ids`` carries
        the ids :func:`_merge_is_safe` named.
      - ``"invalid"`` — malformed input :func:`merge_steps` refuses (fewer than
        two distinct ids, unknown id, non-canonical numbering, mixed scope, or
        an invalid merge graph); the ``DetailError`` is mapped, not raised.

    Mints **no** ``review.Recommendation``: unlike
    :func:`plan_tool.launcher.escalate_to_split`, the bridge is called from an
    already-existing ``granularity-merge`` finding, so it carries only the
    bridge outcome and any preview/apply :class:`MergeResult`.
    """

    outcome: str
    requested_ids: list[int]
    merge_result: Optional[MergeResult] = None
    blocking_ids: list[int] = field(default_factory=list)
    # Set only on the ``"applied"`` path when the fold persisted but re-authoring
    # the merged step raised — the plan is folded-but-unauthored. ``None`` on a
    # clean apply and on every non-``applied`` outcome.
    apply_error: Optional[str] = None


def merge_bridge(
    plan_path: Path,
    *,
    merge_ids: list[int],
    allow_merge: bool,
    title: Optional[str] = None,
    yes: bool = False,
    repo_root: Path,
    invoker: DetailInvoker = shell_detail_invoker,
    reporter: Optional[ProgressReporter] = None,
    run_logger: Optional[RunLogWriter] = None,
    prompt_fn: Optional[Callable[[str], str]] = None,
    budget: IterativeBudget = IterativeBudget(enabled=False),
) -> MergeBridgeResult:
    """Apply-or-recommend a merge remedy around :func:`merge_steps`.

    The merge instance of the apply-or-recommend gate shape (after
    :func:`plan_tool.launcher.escalate_to_split`,
    :func:`plan_tool.scope_out.scope_out_step`, and
    :func:`plan_tool.reground.reground_bridge`). Keeps :func:`merge_steps` the
    only structural executor: this layer owns opt-in, confirmation, and outcome
    mapping so an automated walk gets a structured result — never a raised
    :class:`DetailError` — for the applied / recommended / unsafe / invalid
    paths. Gate order (every path but ``"applied"`` mutates nothing and spends
    no Claude — the dry-run preview passes ``author_details=False``):

      1. Re-parse the plan from disk — never trust an in-memory ``Plan``.
      2. Validation + preview gate: run ``merge_steps(dry_run=True,
         author_details=False)``, authoritative for malformed inputs. On success
         its :class:`MergeResult` is the recommended-path preview; a caught
         :class:`DetailError` is classified — attributable run-state blockers
         (:func:`_merge_is_safe` on a set that cleared the malformed guards) →
         ``"unsafe"``, everything else → ``"invalid"``.
      3. Opt-in gate: ``allow_merge=False`` → ``"recommended"``, no prompt.
      4. Confirm gate: ``yes=True`` bypasses the prompt (still after all
         validity + safety gates); otherwise :func:`_confirm_merge` (default NO,
         non-TTY auto-declines) must assent or the outcome is ``"recommended"``.
      5. Apply: real :func:`merge_steps` with the caller's seams; ``"applied"``.
         ``merge_steps`` writes the folded plan before re-authoring / archiving,
         so an EXPECTED failure past the write — an authoring :class:`DetailError`
         or a filesystem :class:`OSError` — is caught: if the fold persisted it
         is ``"applied"`` with ``apply_error`` (folded-but-unauthored); a
         pre-write ``DetailError`` → ``"invalid"``; a pre-write ``OSError``
         re-raises. An unexpected exception (a bug) is not caught — it
         propagates so the defect surfaces rather than masking as a merge.
    """
    plan_path = Path(plan_path)
    requested = sorted({int(i) for i in merge_ids})

    # 2. Validation + preview gate. ``merge_steps`` dry-run stays authoritative
    #    for malformed inputs; a refusal is classified, never re-raised.
    try:
        preview = merge_steps(
            plan_path,
            merge_ids=merge_ids,
            title=title,
            repo_root=repo_root,
            author_details=False,
            dry_run=True,
        )
    except DetailError:
        # Parse the plan only on the refusal path — the common recommend-only
        # path below never needs it (``merge_steps`` already parsed the file),
        # so the up-front parse would be pure duplicate I/O per finding.
        # Attribute the refusal to run-state blockers only when the set cleared
        # the malformed guards (>=2 distinct known ids, canonical plan); else it
        # is a malformed / scope / graph refusal → ``invalid``.
        plan = parse_plan(plan_path)
        id_set = {s.id for s in plan.steps}
        canonical = [s.id for s in plan.steps] == list(
            range(1, len(plan.steps) + 1)
        )
        if len(requested) >= 2 and set(requested) <= id_set and canonical:
            safe, blocking = _merge_is_safe(plan, requested)
            if not safe:
                return MergeBridgeResult(
                    outcome="unsafe",
                    requested_ids=requested,
                    blocking_ids=blocking,
                )
        return MergeBridgeResult(outcome="invalid", requested_ids=requested)

    # 3. Opt-in gate — recommend the safe, valid preview without prompting.
    if not allow_merge:
        return MergeBridgeResult(
            outcome="recommended", requested_ids=requested, merge_result=preview
        )

    # 4. Confirm gate. ``yes`` bypasses the prompt; else ``_confirm_merge`` owns
    #    the default-NO / non-TTY-declines policy.
    if not yes:
        plan = parse_plan(plan_path)
        member_steps = [plan.step_by_id(i) for i in preview.folded_ids]
        confirm_fn = prompt_fn if prompt_fn is not None else input
        if not _confirm_merge(
            confirm_fn,
            steps_to_merge=member_steps,
            merged_title=preview.merged_title,
        ):
            return MergeBridgeResult(
                outcome="recommended",
                requested_ids=requested,
                merge_result=preview,
            )

    # 5. Apply branch. See the docstring step 5 for the never-raise contract.
    #    The fold persists on disk before re-authoring / archiving, so an
    #    EXPECTED failure past the write — a validation ``DetailError`` or a
    #    filesystem ``OSError`` (detail migrate/archive) — is reported as the
    #    applied-but-unauthored fold, never leaked. A pre-write ``DetailError``
    #    is the malformed-set ``invalid`` mapping; a pre-write ``OSError`` has no
    #    partial mutation, so it re-raises. An UNEXPECTED exception (a real bug)
    #    is deliberately NOT caught — it propagates so the defect surfaces.
    try:
        result = merge_steps(
            plan_path,
            merge_ids=merge_ids,
            title=title,
            repo_root=repo_root,
            invoker=invoker,
            reporter=reporter,
            run_logger=run_logger,
            prompt_fn=prompt_fn,
            budget=budget,
        )
    except (DetailError, OSError) as exc:
        # Did the fold reach disk? A half-written / unparseable plan means the
        # write mutated it — treat a parse failure here as "mutated" so it can
        # never mask ``exc`` into a raised error (never-raise contract).
        try:
            folded = len(parse_plan(plan_path).steps) < len(preview.renumber)
        except Exception:
            folded = True
        if folded:
            return MergeBridgeResult(
                outcome="applied",
                requested_ids=requested,
                apply_error=str(exc),
            )
        if isinstance(exc, DetailError):
            return MergeBridgeResult(outcome="invalid", requested_ids=requested)
        raise  # pre-write OSError: genuine infra failure, nothing mutated
    return MergeBridgeResult(
        outcome="applied", requested_ids=requested, merge_result=result
    )


def _detail_step_input_hash(
    plan_path: Path, step: Step, *, project_context: str = ""
) -> str:
    """SHA-256 hex of the inputs that, when changed, invalidate a cached
    detail body.

    Keyed by plan slug + step id + title + complexity + files +
    depends_on. The plan slug guards against cross-plan collisions (two
    different plans can have step id 1; their checkpoint directories
    are namespaced but the hash is independent). ``files`` and
    ``depends_on`` are passed through as lists so order matters — a
    reordered ``files:`` list changes the prompt's file-contents block
    (``_format_files_contents_block``) and the cache should miss.

    **Intentionally narrow.** This hash is the recovery key for the
    "successful parse → failed durable write" scenario the resume
    feature was built for, not a general-purpose prompt-content hash.
    The following inputs to ``render_detail_prompt`` are *not* hashed
    and will silently serve a stale cache when edited between runs:

    - **File contents.** Editing the source files listed in
      ``step.files`` does not invalidate; the cache replays the body
      generated against the old contents.
    - **Plan-level metadata** (``plan.title``, ``plan.status``,
      ``plan.priority``).
    - **Sibling detail files** discovered by ``_discover_siblings``.
    - **Plan References block** lifted from the plan body.
    - **The scope fence** — ``plan.intent``, ``step.intent``, and the
      guardrail sections lifted from the plan body.
    - **Lessons** loaded by ``render_lessons_block(load_lessons(...))``.
    - **Heuristic-already-done hits** from ``heuristic_already_done``.

    Confirmed project context is the deliberate exception: it is a durable
    scope boundary, so changing it invalidates the recovery cache.

    If the user edits any of those between runs and wants a fresh
    body, they should pass ``--no-resume`` (or ``--force``, which
    bypasses the cache entirely). Widening the hash to cover them
    would defeat resume in the common cross-step iteration case (run
    detail across N steps; lessons / siblings change after each).
    """
    payload: dict[str, object] = {
        "plan_slug": _plan_slug(plan_path),
        "step_id": step.id,
        "title": step.title,
        # Stored as the enum value (``"low"`` / ``"medium"`` / ``"high"``)
        # so JSON serialization is stable; ``None`` hashes distinctly.
        "complexity": step.complexity.value if step.complexity else None,
        "files": list(step.files),
        "creates": list(step.creates),
        "depends_on": list(step.depends_on),
    }
    if project_context:
        payload["project_context"] = project_context
    return compute_input_hash(payload)


def _log_parse_failure(
    *,
    repo_root: Path,
    plan_path: Path,
    step_id: int,
    attempt: int,
    raw_response: str,
) -> Optional[Path]:
    """Persist a failed claude response to ``.plan-tool/parse-failures/``.

    Captures the raw text that ``parse_detail_response`` rejected so a
    later debugging pass can tell *why* it failed — preamble, missing
    section, fenced wrapper that didn't strip cleanly, etc. The retry
    loop in :func:`generate_detail` is the only caller today; it
    invokes this *before* re-prompting so the original (pre-suffix)
    response is what lands on disk.

    Path: ``<repo_root>/.plan-tool/parse-failures/<plan_slug>/<NN>-attemptK-<ts>.txt``.
    Mirrors the ``.plan-tool/checkpoints/<slug>/`` and
    ``.plan-tool/runs/<slug>/`` per-slug conventions so users only have
    one place to look for operational state.

    Returns the written path on success; ``None`` on any I/O error. The
    caller treats this as best-effort — a logging failure must not
    derail the parse-retry flow it's there to debug.
    """
    # Microseconds keep the historic step/attempt/timestamp filename shape
    # while making independently started detail runs collision-free.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result = store_model_response_sidecar(
        repo_root=repo_root,
        producer_slug=_plan_slug(plan_path),
        receipt_identity=f"{step_id:02d}-attempt{attempt}-{ts}",
        raw_response=raw_response,
    )
    if result.outcome is ModelResponseSidecarOutcome.WRITTEN:
        return result.path
    return None


def _archive_existing_detail(output_path: Path) -> Optional[Path]:
    """Move the canonical detail file at ``output_path`` into ``archive/``.

    Used right before overwriting an existing detail file so the prior
    content is preserved instead of clobbered. The new file is written
    at the canonical path; the old one lands at
    ``output_path.parent/archive/<stem>.<UTC-ts>.md`` (renaming the
    archived copy, not the new one, so downstream tooling keeps finding
    the active detail under its expected slug).

    Returns the archive destination on success, ``None`` if there was
    no file to archive or the move failed (best-effort: a permissions /
    cross-device error must not derail the write the caller is about
    to perform, since the user has already explicitly opted into the
    replacement).
    """
    if not output_path.is_file():
        return None
    archive_dir = output_path.parent / "archive"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{output_path.stem}.{ts}.md"
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        # Defensive collision avoidance — two archives in the same UTC
        # second is unlikely but cheap to guard. Fall back to a
        # microsecond-precision suffix.
        if dest.exists():
            ts_us = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            dest = archive_dir / f"{output_path.stem}.{ts_us}.md"
        output_path.rename(dest)
    except OSError:
        return None
    return dest


def _archive_orphan_details(
    output_path: Path, step_id: int
) -> list[Path]:
    """Move stale ``NN-*.md`` siblings for this step into ``archive/``.

    After a step's title is edited (or the model produced a different
    slug than a prior run), the previously-written detail file is
    stranded next to the new one — the plan's ``step.detail`` only
    points at the just-written file. Sweep the strays into
    ``output_path.parent/archive/`` so the plan-details directory
    stays clean and the orphans remain recoverable.

    Pattern: any file in ``output_path.parent`` whose name starts with
    ``{step_id:02d}-`` and ends with ``.md`` *except* the canonical
    just-written file (``output_path.name``). The canonical file is
    never moved.

    On an archive-name collision (rare: same orphan name already in
    ``archive/`` from a prior sweep), the new file is renamed with a
    UTC timestamp suffix to avoid clobbering. Per-file ``OSError`` is
    swallowed so a missing-perm or cross-device-link issue can't break
    the detail flow — the orphan stays where it is and the caller
    proceeds.

    Returns the list of archive destinations actually written.
    """
    plan_dir = output_path.parent
    if not plan_dir.is_dir():
        return []
    archive_dir = plan_dir / "archive"
    prefix = f"{step_id:02d}-"
    moved: list[Path] = []
    for sibling in plan_dir.glob(f"{prefix}*.md"):
        if sibling.name == output_path.name:
            continue
        if not sibling.is_file():
            continue
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / sibling.name
            if dest.exists():
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                dest = archive_dir / f"{sibling.stem}.{ts}.md"
            sibling.rename(dest)
            moved.append(dest)
        except OSError:
            continue
    return moved


def _format_tests_directive(change_type: Optional[ChangeType]) -> str:
    """Render the per-step test directive for the ``## Tests`` section.

    Single wording source for both the authoring prompt
    (:func:`render_detail_prompt`) and the reviewing prompt
    (:func:`render_detail_quality_prompt`) — feeding both renders from
    here is the anti-drift contract, so the shape the author is told to
    write and the shape the reviewer enforces cannot diverge.

    Code steps (``feature`` *and* ``refactor``) share one directive: name
    the tests and require them green. **The former per-type test-*ordering*
    contract was removed 2026-07-30 — do not reintroduce it.** It told
    ``refactor`` steps to write characterization tests that pass *before*
    the change; that was measured against every refactor step in
    this repo's history and found 81–89% of them cannot satisfy it for
    legitimate reasons — a refactor that renames or re-shapes what the
    tests name leaves those tests unable to import, let alone pass, against
    pre-change source. The directive asserted a property most refactor
    steps cannot have, so it was withdrawn rather than mechanized.

    Returns a block that leads with its own blank line (so it opens a
    ``### …`` sub-section *within* the existing ``## Tests`` section — never
    a new output H2, so ``parse_detail_file_sections(...).get("tests")``
    still captures it) for a classified step, and the empty string for an
    unclassified (``None``) step. The caller appends the result to the end
    of the Tests guidance line with no preceding newline, so the empty
    case collapses to nothing and the unclassified prompt keeps today's
    exact whitespace shape (zero prompt delta).
    """
    if change_type in (ChangeType.REFACTOR, ChangeType.FEATURE):
        return (
            "\n\n### Tests for this step\n\n"
            "Enumerate the tests this step adds or changes and name the "
            "behavior each one covers. State the green-before-done gate: "
            "every one must be green before this step is considered "
            "finished. Cover the behavior the step actually changes — do "
            "not pad the roster to satisfy the gate."
        )
    if change_type == ChangeType.NON_CODE:
        return (
            "\n\n### Verification (non-code step)\n\n"
            "This is a **non-code** step — it changes no production code. "
            "Enumerate verification appropriate to the artifacts (config "
            "validation, doc link and accuracy checks) rather than unit "
            "tests."
        )
    return ""


def _format_step_files_block(step: Step) -> str:
    if not step.files and not step.creates:
        return "(no files declared)"
    lines = [f"- `{f}`" for f in step.files]
    lines += [f"- `{f}` (new — created by this step)" for f in step.creates]
    return "\n".join(lines)


def _capture_detail_lessons_after_validation(
    *,
    extract_lessons: bool,
    body: str,
    did_structural_split: bool,
    validated: bool,
    plan: Plan,
    plan_path: Path,
    step: Step,
    repo_root: Path,
    lessons_invoker: Optional[LessonsInvoker],
    reporter: Optional[ProgressReporter],
    strict_check: bool,
    run_logger: Optional[RunLogWriter],
    equivalence_invoker: Optional[EquivalenceInvoker],
    detail_path: Optional[Path] = None,
) -> None:
    """Distill lessons only after a clean detail-quality pass.

    Capture from an unaudited first write was the defect (BUG closed
    2026-08-03): a later audit can delete prose the store already
    generalized. Skip unless ``validated`` (iterate exited with 0 open
    findings). Best-effort — failures never roll back the detail file.
    """
    if not extract_lessons or not body or did_structural_split:
        return
    if not validated:
        tool(
            f"lesson extraction skipped for step {step.id}: detail has "
            "not survived a clean detail-quality pass (0 open findings). "
            "Pass --lessons with --iterate; capture runs only when that "
            "loop converges clean."
        )
        return
    detail_body = body
    if detail_path is not None and detail_path.is_file():
        try:
            detail_body = detail_path.read_text(encoding="utf-8")
        except OSError:
            pass
    try:
        inv = lessons_invoker
        if inv is None:
            from plan_tool.shell import claude_invoke as inv  # type: ignore[assignment]
        result = extract_and_append_detail_lessons(
            plan=plan,
            plan_path=plan_path,
            step=step,
            detail_body=detail_body,
            repo_root=repo_root,
            invoker=inv,
            reporter=reporter,
            strict_check=strict_check,
            run_logger=run_logger,
            equivalence_invoker=equivalence_invoker,
        )
        n_general, n_project = result
        if (n_general + n_project) > 0:
            # Name the scope-gate demotion: a lesson the model filed as general
            # that landed in project is a routing decision the operator should
            # see, not a silent reclassification.
            routed = result.n_general_routed_to_project
            routed_note = f" ({routed} routed to project)" if routed else ""
            print(
                f"        captured {n_general} general + "
                f"{n_project} project lesson(s){routed_note}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 — best-effort
        tool(
            f"lesson extraction failed for step "
            f"{step.id} ({exc}); detail file is unaffected"
        )


def extract_and_append_detail_lessons(
    *,
    plan: Plan,
    plan_path: Path,
    step: Step,
    detail_body: str,
    repo_root: Path,
    invoker: "Callable[[str], tuple[int, str]]",
    reporter: Optional[ProgressReporter] = None,
    strict_check: bool = False,
    equivalence_invoker: Optional[EquivalenceInvoker] = None,
    run_logger: Optional[RunLogWriter] = None,
) -> AppendLessonsResult:
    """Distill lessons from this step's detail run and append them.

    Captures any takeaway that would make future ``plan-tool create`` /
    ``plan-tool detail`` / ``plan-tool reconcile-plan`` runs more correct or
    complete with less work — not limited to misinterpretations of the
    create-time proposal. Returns an :class:`AppendLessonsResult` (which
    destructures to ``(n_general_added, n_project_added)``) after dedupe,
    summing the canonical-sink and per-plan-pending writes.

    ``strict_check`` / ``equivalence_invoker`` are forwarded to the
    canonical :func:`append_lessons` call only — the per-plan pending
    quarantine has no strict-check pass. Dropped findings from the
    canonical write are surfaced on the result.

    Routes bullets away from canonical sinks that the active plan
    targets: if ``lessons/general.md`` (or ``.plan-tool/lessons/project.md``)
    is in the plan's ``files:`` set, the matching bucket lands in a
    per-plan quarantine file
    (``.agents/skills/plan-tool/lessons/pending/<plan-slug>.md``)
    instead of the canonical sink. Stops `detail`'s distillation pass
    from corrupting the very lessons file the plan is scrubbing.
    ``load_lessons`` deliberately does not read from the quarantine
    directory, so bullets there are invisible to the prompt that
    produced them.
    """
    prompt = _render_extract_detail_lessons_prompt(
        plan=plan,
        step=step,
        detail_body=detail_body,
        repo_root=repo_root,
    )
    if reporter is None:
        reporter = StderrReporter()
    handle = reporter.start_step(1, 1, f"Distilling lessons from step {step.id}")
    start = time.monotonic()
    # Without a sink this call is spent but unrecorded — ``_emit_call_end``
    # no-ops when none is installed (see BACKLOG #176-#178).
    if run_logger is not None:
        run_logger.claude_call_start(
            phase="distill_lessons",
            attempt=1,
            prompt_bytes=len(prompt.encode("utf-8")),
            prompt_sha256=hash_prompt(prompt),
            step_id=step.id,
        )
        sink = run_logger.bind_shell_sink(phase="distill_lessons", attempt=1)
    else:
        sink = contextlib.nullcontext()
    with sink:
        exit_code, stdout = invoker(prompt)
    elapsed = time.monotonic() - start
    if exit_code != 0 or not stdout.strip():
        handle.fail(elapsed, f"exit {exit_code}, {len(stdout)} bytes")
        return AppendLessonsResult(0, 0)
    parsed = parse_lessons_extract_response(stdout)
    if parsed is None:
        handle.fail(elapsed, "unparseable JSON")
        return AppendLessonsResult(0, 0)
    general, project = parsed
    handle.complete(elapsed, len(stdout.encode("utf-8")))
    plan_slug = _plan_slug(plan_path)
    source_tag = f"detail:{plan_slug}#{step.id}"

    # Per-plan scope guard: route bullets whose canonical sink is in
    # the active plan's ``files:`` set into the per-plan pending file
    # instead. Lazy-import scope_guard (call-time) to keep the
    # module-load graph a tree, matching the pattern used elsewhere
    # in this module.
    from plan_tool.scope_guard import compute_in_scope_paths

    in_scope = compute_in_scope_paths(plan, plan_path, repo_root)
    # ``general`` lives at ``~/.plan-tool/lessons/general.md`` (outside any
    # repo), so a plan can never declare it in ``files:`` — its bullets
    # always land in the canonical sink. Only the per-repo ``project.md``
    # can be in a plan's scope; when it is, redirect those bullets to the
    # per-plan pending file rather than corrupting the sink the plan is
    # actively scrubbing.
    project_in_scope = lessons.project_path(repo_root).resolve() in in_scope

    canonical_general = general
    canonical_project = () if project_in_scope else project
    pending_general = ()
    pending_project = project if project_in_scope else ()

    canonical = append_lessons(
        repo_root,
        general=canonical_general,
        project=canonical_project,
        source=source_tag,
        strict_check=strict_check,
        equivalence_invoker=equivalence_invoker,
    )
    n_general_pending = 0
    n_project_pending = 0
    if pending_general or pending_project:
        n_general_pending, n_project_pending = append_pending_lessons(
            repo_root,
            plan_slug=plan_slug,
            general=pending_general,
            project=pending_project,
            source=source_tag,
        )
    return AppendLessonsResult(
        n_general_added=canonical.n_general_added + n_general_pending,
        n_project_added=canonical.n_project_added + n_project_pending,
        general_dropped=canonical.general_dropped,
        project_dropped=canonical.project_dropped,
        n_general_routed_to_project=canonical.n_general_routed_to_project,
    )


def _render_extract_detail_lessons_prompt(
    *,
    plan: Plan,
    step: Step,
    detail_body: str,
    repo_root: Path,
) -> str:
    """Render ``prompts/extract-lessons-detail.md`` with the run's context."""
    template_path = prompts_dir() / "extract-lessons-detail.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    lessons_block = render_lessons_block(load_lessons(repo_root))
    already_implemented_block = _format_already_implemented_block(
        plan, step, repo_root
    )
    files_inline = (
        ", ".join(f"`{f}`" for f in step.all_files) if step.all_files else "(none)"
    )
    depends_on = ", ".join(str(d) for d in step.depends_on) if step.depends_on else "(none)"
    complexity = step.complexity.value if step.complexity else "unknown"
    return template.safe_substitute(
        plan_title=plan.title,
        step_id=str(step.id),
        step_title=step.title,
        step_complexity=complexity,
        step_files_inline=files_inline,
        step_depends_on=depends_on,
        already_implemented_block=already_implemented_block,
        detail_body_block=detail_body.strip(),
        lessons_block=lessons_block,
    )


def _format_files_contents_block(
    step: Step, repo_root: Path, *, max_file_bytes: int
) -> str:
    """Render `### path` headers + symbol-aware excerpts for declared files.

    Same convention as the file-excerpt renderers in ``review.py`` and
    ``jira.py``: missing files render a ``_(not on disk)_`` marker so
    claude knows to expect a creation, unreadable files render their
    OSError so debugging is possible.
    """
    if not step.all_files:
        return "_no files declared_"
    out: list[str] = []
    for f in step.all_files:
        path = repo_root / f
        if not path.is_file():
            out.append(f"### `{f}` _(not on disk)_\n")
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            out.append(f"### `{f}` _(unreadable: {exc})_\n")
            continue
        candidate_symbols = _derive_symbols(step.title)
        _merge_candidate_symbols(
            candidate_symbols, _derive_file_path_symbols(f)
        )
        excerpt = build_prompt_excerpt(
            f,
            body,
            candidate_symbols,
            max_bytes=max_file_bytes,
        )
        metadata = (
            f"_excerpt_kind: {excerpt.excerpt_kind}; "
            f"fallback_reason: {excerpt.fallback_reason or 'none'}; "
            f"truncated: {str(excerpt.truncated).lower()}_"
        )
        out.append(f"### `{f}`\n\n{metadata}\n\n```\n{excerpt.text}\n```\n")
    return "\n".join(out)


def _discover_siblings(output_path: Path) -> list[Path]:
    """List existing markdown files in ``output_path``'s parent dir.

    Excludes the path itself (so re-running with ``--force`` doesn't feed
    the previous draft back into the prompt as a sibling). Returns a
    sorted list for deterministic prompt output.
    """
    parent = output_path.parent
    if not parent.is_dir():
        return []
    return sorted(
        p for p in parent.glob("*.md")
        if p.resolve() != output_path.resolve()
    )


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Return ``path`` expressed relative to ``repo_root`` as a posix string.

    Falls back to the absolute path string (with a stderr warning) when
    ``path`` doesn't live under ``repo_root`` — rare in practice, but
    can happen when the user pinned ``--repo-root`` to a directory that
    doesn't contain the chosen plan layout.
    """
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        warn(
            f"detail path {path} is not under repo root "
            f"{repo_root}; storing absolute path in step.detail"
        )
        return str(path.resolve())
    return rel.as_posix()


def _format_sibling_details_block(
    sibling_paths: Sequence[Path], *, max_file_bytes: int
) -> str:
    """Render existing sibling detail files as a tone/structure reference.

    Skips paths that don't exist or aren't files (defensive — the
    orchestrator filters before calling, but this stays consistent with
    the file-contents block's tolerance for absent paths).
    """
    if not sibling_paths:
        return "_no sibling detail files yet_"
    out: list[str] = []
    for path in sibling_paths:
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            out.append(f"### `{path.name}` _(unreadable: {exc})_\n")
            continue
        require_supported_detail_format_version(body, path=path)
        snippet = body[:max_file_bytes]
        truncated = "\n… _(truncated)_" if len(body) > max_file_bytes else ""
        out.append(f"### `{path.name}`\n\n{snippet}{truncated}\n")
    if not out:
        return "_no sibling detail files yet_"
    return "\n".join(out)


def _format_prior_body_block(prior_body: str) -> str:
    """Render the folded members' full detail bodies for a merge re-author.

    Unlike :func:`_format_sibling_details_block` (a tone/structure reference
    truncated at ``_MAX_PROMPT_FILE_BYTES``), this emits ``prior_body``
    **verbatim and untruncated** — the faithful combine input so the merged
    re-author absorbs each member's complete seven-section body, not a ~4 KB
    prefix. Empty (inert) for every non-merge call, so the section vanishes
    from the rendered prompt.
    """
    if not prior_body.strip():
        return ""
    return (
        "### Prior detail bodies being merged "
        "(combine these into one coherent file)\n\n"
        f"{prior_body.strip()}\n"
    )


def _print_detail_budget_breakdown(
    step: Step, budget: PromptBudget, *, stream: Optional[TextIO] = None
) -> None:
    """Print one step's full prompt-budget breakdown for ``detail --dry-run``.

    Inspection only: prints at **every** level (including ``ok``) to stderr, so
    a piped ``detail --dry-run`` still yields a clean prompt on stdout while the
    operator sees the headroom breakdown on the terminal. Records no telemetry
    (dry-run sends nothing).
    """
    out = stream if stream is not None else sys.stderr
    print(
        render_budget_summary(
            budget,
            surface=f"detail step {step.id}",
            blocks_label="blocks",
            max_blocks=None,
        ),
        file=out,
    )
