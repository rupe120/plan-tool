"""plan-tool reconcile-plan: plan-vs-codebase reality check.

Audits a plan's intent against the current state of the codebase before
execution begins. Distinct from ``run --mode check`` (which audits code for a
specific step's files) and ``detail --reconcile`` (which audits whether a
done step actually delivered what it promised).

The deterministic checks — file existence, already-done heuristic, dependency
validation — run locally with no shell-out. Claude's semantic review is
layered on top via an injectable ``Invoker``: when ``claude`` isn't on PATH,
or the caller passes ``invoker=None``, the deterministic report still prints
and the Claude section is replaced by a short explanation.

Pure functions (``check_file_existence``, ``heuristic_already_done``,
``validate_deps``, ``assemble_report``, ``render_review_prompt``) return
structured data; only ``review_plan`` orchestrates, and only the CLI formats.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path, PurePosixPath
from string import Template
from typing import TYPE_CHECKING, Callable, Iterable, Literal, Mapping, Optional, Sequence

if TYPE_CHECKING:
    from plan_tool.concept_tree import ConceptNode, ConceptTree

from plan_tool.audit_shapes import (
    AuditShapeAdvisory,
    AuditShapeFindingEvidence,
    evaluate_arm_clustering,
)
from plan_tool.lessons import (
    AppendLessonsResult,
    EquivalenceInvoker,
    LessonEntry,
    append_lessons,
    load_lessons,
    parse_lessons_extract_response,
    render_lessons_block,
)
from plan_tool.backend import spawn_cwd_from_repo_root
from plan_tool.convergence import is_blocking_impact
from plan_tool.detail_artifacts import (
    DetailArtifactResolution,
    DetailFormatError,
    require_supported_detail_format_version,
    resolve_detail_artifact,
)
from plan_tool.locator import slug_from_filename
from plan_tool.pathutil import normalize_declared_path
from plan_tool.project_profile import (
    project_profile_context,
    render_project_context_block,
)
from plan_tool.parser import (
    ParseError,
    _split_frontmatter,
    parse_plan,
    split_body_sections,
)
from plan_tool.scope_fence import _excise_fenced_code, _fenced_code_spans
from plan_tool.prompt_excerpt import build_prompt_excerpt, clip_text_to_byte_budget
from plan_tool.run_log import hash_prompt
from plan_tool.progress import ProgressReporter, StderrReporter
from plan_tool.claude_errors import ClaudeFailureKind
from plan_tool.shell import (
    ClaudeInvokeOutcome,
    claude_invoke,
    claude_invoke_outcome,
    suppress_prompt_budget_backstop,
)
from plan_tool.renderer import prompts_dir
from plan_tool.response_contract import (
    FINDINGS_RESPONSE_CONTRACT,
    MarkdownSectionsContract,
    ResponseSection,
)
from plan_tool.prompt_budget import estimate_prompt_budget, maybe_warn_prompt_budget
from plan_tool.context_window import active_context_window
from plan_tool.schema import ChangeType, Plan, Step, StepScope, StepStatus
from plan_tool.scope_fence import (
    collapse_intent_to_one_line,
    is_placeholder_intent,
)
from plan_tool.style import tool
from plan_tool.telemetry import (
    code_fingerprint_digest,
    record_code_reveals_split,
    record_prompt_budget,
)


Invoker = Callable[[str], tuple[int, str]]


@dataclass(frozen=True)
class _PlanAuditInvocation:
    """Audit invocation facts that preserve the classified failure kind."""

    exit_code: int
    stdout: str
    failure_kind: Optional[ClaudeFailureKind] = None


PlanAuditInvokerResult = tuple[int, str] | _PlanAuditInvocation
PlanAuditInvoker = Callable[[str], PlanAuditInvokerResult]


def _plan_audit_invocation_parts(
    result: PlanAuditInvokerResult,
) -> tuple[int, str, Optional[ClaudeFailureKind]]:
    """Read an audit adapter result without changing ordinary tuple callers."""
    if isinstance(result, _PlanAuditInvocation):
        return result.exit_code, result.stdout, result.failure_kind
    exit_code, stdout = result
    return exit_code, stdout, None


def build_low_impact_demotion_lookup(repo_root: Path):
    """Lazily load the operation-scoped calibration lookup.

    ``telemetry_analysis`` reaches review-adjacent modules during import, so
    defer that import until an audit actually needs its read-only rule.
    """
    from plan_tool.telemetry_analysis import (
        build_low_impact_demotion_lookup as build_lookup,
    )

    return build_lookup(repo_root)


# Source extensions the heuristic opens. Each category gets its own pattern
# list and minimum-hit threshold (see ``_scan_for_heuristic_hit``):
#   - code: substring patterns (``def foo``, ``class Foo``); flag on first
#     match. Mirrors today's behavior.
#   - prose: line-anchored markdown headers (``# Foo``, ``## Foo``, …); flag
#     only when ≥``_PROSE_MIN_HITS`` matches in the same file. Two-header
#     threshold drops false positives on docs that incidentally mention a
#     symbol once.
#   - config: substring patterns shaped like JSON/TOML keys/sections; flag
#     on first match. Same threshold as code — config keys are
#     specific enough that incidental matches are rare.
_CODE_EXTS = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".swift",
    }
)
_PROSE_EXTS = frozenset({".md"})
_CONFIG_EXTS = frozenset({".toml", ".json"})
# Extensions ``heuristic_already_done`` actually opens; a file outside this set
# is never scanned, so its absence of a hit is not evidence of un-built code.
_SCANNABLE_EXTS = _CODE_EXTS | _PROSE_EXTS | _CONFIG_EXTS

# Words that appear in step titles but carry no identifier signal. Kept small
# and conservative — the heuristic is allowed to have false negatives; false
# positives are worse because they nag the user to run ``reconcile``.
_TITLE_STOPWORDS = frozenset(
    {
        "a",
        "add",
        "all",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "build",
        "by",
        "create",
        "fix",
        "for",
        "from",
        "hook",
        "implement",
        "in",
        "into",
        "is",
        "it",
        "just",
        "make",
        "new",
        "now",
        "of",
        "on",
        "one",
        "only",
        "onto",
        "or",
        "out",
        "plan",
        "refactor",
        "set",
        "setup",
        "so",
        "step",
        "support",
        "that",
        "the",
        "this",
        "to",
        "update",
        "use",
        "using",
        "via",
        "we",
        "when",
        "what",
        "wire",
        "with",
        "you",
    }
)

_PATH_SYMBOL_STOPWORDS = frozenset(
    {
        "__init__",
        "app",
        "bin",
        "build",
        "cli",
        "cmd",
        "config",
        "dist",
        "doc",
        "docs",
        "lib",
        "main",
        "module",
        "package",
        "pkg",
        "script",
        "scripts",
        "src",
        "test",
        "tests",
        "util",
        "utils",
    }
)

# Substring patterns hunted in source files. Matched with word-boundary
# regex (see ``_count_pattern_occurrences``) so ``def parser`` no longer
# false-positives on ``def parser_setup`` — the historical substring
# behavior was the dominant source of false positives in the heuristic.
_PATTERN_TEMPLATES = (
    "def {token}",
    "class {cap}",
    "function {token}",
    "const {token}",
    "let {token}",
    "var {token}",
    "export function {token}",
    "export class {cap}",
    "export const {token}",
)

# Prose patterns are markdown headers anchored to the start of a line. Inline
# mentions of a symbol in body text don't count — that ratio of false positives
# was the whole reason ``.md`` was excluded from the heuristic before.
_PROSE_PATTERN_TEMPLATES = (
    "# {cap}",
    "## {cap}",
    "### {cap}",
)

# Config patterns try to look like keys/sections in JSON or TOML. Both
# casings are checked because plan-tool's own configs (e.g. ``pyproject.toml``)
# mix kebab-case CLI names with PascalCase Python symbols.
_CONFIG_PATTERN_TEMPLATES = (
    '"{token}"',
    '"{cap}"',
    "{token} =",
    "{cap} =",
    "[{token}]",
    "[{cap}]",
)

_MAX_HEURISTIC_BYTES = 32768
_MAX_PROMPT_FILE_BYTES = 4096
# Cap used by deterministic body-parsing checks (detail body completeness,
# files coherence). These never ship the parsed text to claude, so the
# prompt-context truncation that ``_MAX_PROMPT_FILE_BYTES`` enforces is
# inappropriate here — past 4 KB, H2 sections in larger detail files would
# silently disappear and the check would report them as missing. 1 MB is
# well above any plausible detail-file size while still bounding pathological
# input.
_MAX_DETAIL_PARSE_BYTES = 1_048_576

# Minimum hits in one file before flagging a prose match. Two means a single
# incidental mention of a token in a doc doesn't trigger; two header-shaped
# matches do.
_PROSE_MIN_HITS = 2

# Threshold above which we treat MISSING_PARENT warnings as a systemic
# path-style mismatch rather than per-step bugs. 0.8 is conservative enough
# to skip plans where one or two paths simply moved, but tight enough to
# catch the common "wrong repo root" case where every declared file
# resolves under the wrong directory.
_PATH_STYLE_MISMATCH_THRESHOLD = 0.8

# Number of representative offending paths to surface in the diagnostic.
# More than 3 starts to look like the per-step list we're trying to replace.
_PATH_STYLE_EXAMPLE_LIMIT = 3


class FileExistence(str, Enum):
    OK = "ok"
    NEW = "new"  # file missing but parent dir exists — expected for creators
    MISSING_PARENT = "missing_parent"  # parent dir missing — path is suspect


@dataclass(frozen=True)
class FileCheck:
    path: str
    status: FileExistence
    # True when the path came from the step's ``creates:`` list — a file
    # the step brings into existence. Created files are expected to be
    # absent until the step runs, so MISSING_PARENT / NEW never flag them;
    # the only failure mode is a DONE step that never produced the file.
    created: bool = False


@dataclass(frozen=True)
class StepFileCheck:
    step_id: int
    files: list[FileCheck]


@dataclass(frozen=True)
class HeuristicHit:
    step_id: int
    file: str
    symbol: str
    pattern: str


@dataclass(frozen=True)
class DepIssue:
    step_id: int
    depends_on: int
    reason: str  # "unknown"


@dataclass(frozen=True)
class Redirect:
    """One ``## Redirect`` block parsed out of a run-reconcile finding's body.

    Emitted per finding by ``prompts/run-reconcile.md`` (step 2 of the
    Reconcile Subcommand Split plan) when claude judges that a code-side
    finding's root cause lives in the plan/detail rather than the code.
    Consumed by ``cli._cmd_run_reconcile`` (step 4): a populated
    ``Redirect`` short-circuits the finding with a ``[REDIRECT]`` stderr
    line pointing the operator at ``plan-tool detail --reconcile``.

    Absence of the block is signaled by :func:`parse_redirect_block`
    returning ``None``; a present heading with missing labelled lines
    returns a ``Redirect`` whose fields are empty strings so the CLI
    can still surface the redirect (it falls back to ``(unspecified)``
    for an empty ``reason``).

    ``suggested_next`` is preserved as a raw string rather than promoted
    to an enum because the CLI constructs the canonical next command
    itself from the plan slug — this field is informational only.
    """

    reason: str = ""
    suggested_next: str = ""


@dataclass(frozen=True)
class Recommendation:
    """One actionable item extracted from a review run.

    Used by ``plan-tool reconcile-plan-walk`` (and ``review --walk``) to step
    the user through the report's findings interactively. The shape
    intentionally avoids referencing ``Plan`` / ``Step`` Pydantic
    objects so a saved review can be re-loaded and walked without the
    underlying plan file having to be re-parsed.

    ``id`` is stable across re-runs of an unchanged review so the same
    recommendation produces the same identifier (content-addressed via
    the body). ``source`` identifies which review primitive emitted it
    (``"file-check"`` / ``"heuristic"`` / ``"deps"`` / ``"path-style"``
    / ``"claude"``) — useful for filtering and for telemetry. ``body``
    is the human-readable detail; ``suggested_action`` is the
    actionable follow-up command or check, or ``None`` when the review
    primitive doesn't have one.
    """

    id: str
    source: str
    severity: str  # "critical" | "high" | "medium" | "low" | "nit" | "info"
    step_id: Optional[int]
    title: str
    body: str
    suggested_action: Optional[str] = None
    # Triage tags (session 4 follow-up to #29/#27). Populated by
    # ``check_plan_audit`` and ``extract_reconcile_recommendations``
    # from the ``(impact=…, complexity=…)`` pair the plan-audit and
    # reconcile prompts emit, so the iteration loop can short-circuit
    # applies on findings whose complexity outweighs their impact
    # (low+medium/high → skip, medium+high → skip). ``None`` = no
    # triage data → apply by default (the case for deterministic
    # findings and any output that doesn't carry the tag).
    # ``"low" | "medium" | "high"`` when populated.
    impact: Optional[str] = None
    complexity: Optional[str] = None
    # Refuse-and-redirect signal (Reconcile Subcommand Split, step 4).
    # Populated only by :func:`extract_run_reconcile_recommendations`
    # when claude emits a ``## Redirect`` sub-block under the finding
    # bullet (i.e. the code-side audit judged the root cause to live
    # in the plan, not the code). Every other extractor leaves this
    # ``None``. The CLI branches on ``rec.redirect is not None`` to
    # emit the ``[REDIRECT]`` stderr line and short-circuit code apply.
    redirect: Optional[Redirect] = None
    # How a persisted MIXED-STEP purity verdict was obtained. This is set only
    # on ``granularity-split`` findings: ``fresh`` for a live verdict,
    # ``exact-cache`` for an unchanged cache hit, and ``below-floor-reuse``
    # for a trivial-edit cache reuse. Other findings leave it unset.
    purity_verdict_provenance: Optional[str] = None
    # Repo-relative path a deterministic apply can act on. Set only by
    # the MISSING_PARENT branch of :func:`_file_check_recommendation`
    # so :func:`plan_tool.review_walk.file_check_create_target` can
    # offer to move it from the step's ``files:`` into ``creates:`` on
    # apply. ``None`` for every other finding (including the
    # file-check NEW-on-DONE shapes, whose resolution is reconcile, not
    # a path move). Round-trips through the saved-review JSON via
    # ``asdict`` / ``recommendation_from_persisted_mapping``.
    file_path: Optional[str] = None
    # The ``[anchor-slug]`` claude emitted for a plan-audit finding —
    # the human-readable concept key (``cache-invalidation``,
    # ``step3-ordering``) the id fingerprint is derived from. Populated
    # only by :func:`_parse_plan_audit_findings` when the slug contract
    # was honored; ``None`` everywhere else (deterministic findings,
    # sluggless audit bullets). :func:`audit_plan_until_stable` feeds
    # the accumulated slugs back into later passes' prompts so a
    # re-found concept re-uses its slug instead of minting a semantic
    # duplicate.
    anchor: Optional[str] = None
    # Precise-staleness signature (BACKLOG #93). SHA-256 digest of the
    # directive's own target steps' ``(id → title + change_type)`` identity,
    # stamped by the post-audit pass so the structural-remedy walk's stale
    # guard can compare just the directive's targets instead of the whole
    # plan. ``None`` = unknown (legacy sidecars, non-directive recs, or a rec
    # never stamped) → the guard falls back to the coarse whole-plan check.
    # See :func:`plan_tool.review_walk.compute_target_signature`.
    target_signature: Optional[str] = None
    # Fresh findings use the conservative limited state. ``None`` is retained
    # only for persisted findings whose evidence predates this field.
    confidence: Literal["supported", "limited"] | None = "limited"
    # Plan-altitude restatement of a bare-step Correctness finding (the
    # prompt's ``### Restated`` sub-block). Contract: DATA_CONTRACT.md and
    # plan-audit.md's "Property coverage versus delivery mechanisms".
    restated_property: Optional[str] = None


def confidence_value(confidence: Optional[str]) -> str:
    """Return stored evidence support; legacy absence reads as unknown."""
    return confidence if confidence is not None else "unknown"


# Citation fences protect model output at any indentation, beyond Markdown limits.
_FENCE_MARKER_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """Return citation-fence offsets, retaining line endings and unclosed tails."""
    spans: list[tuple[int, int]] = []
    fence_char: Optional[str] = None
    fence_len = 0
    span_start = 0
    pos = 0
    for line in text.splitlines(keepends=True):
        match = _FENCE_MARKER_RE.match(line)
        if match:
            run = match.group(1)
            char, length = run[0], len(run)
            if fence_char is None:
                fence_char, fence_len, span_start = char, length, pos
            elif char == fence_char and length >= fence_len:
                spans.append((span_start, pos + len(line)))
                fence_char = None
        pos += len(line)
    if fence_char is not None:
        spans.append((span_start, len(text)))
    return spans


def indent_bullet_body(body: str) -> str:
    """A finding body for the tail of a markdown bullet, continuation lines
    indented two spaces under it.

    The model quotes plan text in fenced blocks, so a body spans lines at
    whatever indentation it chose. A column-0 fence would end the list item and
    one indented four or more spaces past the item reads as an indented code
    block. Fence delimiter lines (found by :func:`fenced_spans`, the citation
    scanner) are therefore set to the bullet's margin, and every other
    continuation line is dedented by their common margin, so relative
    indentation inside a fence survives. Blank lines stay empty and the text is
    never rewritten or escaped.
    """
    first, sep, rest = body.partition("\n")
    if not sep:
        return first
    lines = rest.split("\n")
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    delimiters: set[int] = set()
    for start, end in fenced_spans(rest):
        delimiters.add(offsets.index(start))
        last = next(k for k in range(len(lines) - 1, -1, -1) if offsets[k] < end)
        if last not in delimiters and lines[last].lstrip()[:3] in ("```", "~~~"):
            delimiters.add(last)
    content = [ln for k, ln in enumerate(lines) if k not in delimiters and ln.strip()]
    margin = min((len(ln) - len(ln.lstrip()) for ln in content), default=0)
    out: list[str] = []
    for k, ln in enumerate(lines):
        if not ln.strip():
            out.append("")
        elif k in delimiters:
            out.append(f"  {ln.lstrip()}")
        else:
            out.append(f"  {ln[margin:]}")
    return first + "\n" + "\n".join(out)


def confidence_label(confidence: Optional[str]) -> str:
    """Render the stored evidence-support value without classifying it.

    No local validation — :func:`recommendation_from_persisted_mapping`
    already rejects an invalid stored value before construction.
    """
    return f"confidence: {confidence_value(confidence)}"


def severity_label(severity: Optional[str]) -> str:
    """Render a finding's severity, defaulting an unset value to INFO."""
    return severity.upper() if severity else "INFO"


# Shared across every ``restated_property`` render site (this function,
# completeness_report.py, review_walk.py, cli/review_cmd.py,
# cli/completeness_phases.py, launcher.py's multi-finding apply bundler) so
# the disclaimer's wording can't drift between them the way independently
# hand-written copies did.
RESTATED_PROPERTY_LABEL = (
    "Plan-altitude restatement (delivered evidence, not a verdict on this "
    "finding)"
)


def restated_property_or_none(rec: Recommendation) -> Optional[str]:
    """Stripped ``restated_property``, or ``None`` for absent/whitespace-only.

    Every render site must treat a whitespace-only value the same as an
    absent one (a bare truthiness check does not); centralized once here
    instead of independently reimplemented at each site.
    """
    value = (rec.restated_property or "").strip()
    return value or None


def format_recommendation_for_apply(rec: Recommendation) -> str:
    """Render one recommendation for a direct apply prompt.

    Includes ``restated_property`` when present -- the Claude call that
    performs the apply edit is the one place a misread citation actually
    gets acted on, so it must see the same evidence the report shows a
    human, not just the finding's own (possibly over-specific) body.
    """
    blocks = [
        f"[{severity_label(rec.severity)}] {rec.title}",
        confidence_label(rec.confidence),
    ]
    body = rec.body.strip()
    if body:
        blocks.append(body)
    restated = restated_property_or_none(rec)
    if restated:
        blocks.append(f"{RESTATED_PROPERTY_LABEL}: {restated}")
    return "\n\n".join(blocks)


def recommendation_from_persisted_mapping(raw: Mapping[str, object]) -> Recommendation:
    """Validate the flat confidence field and restore the nested redirect
    field before constructing a recommendation.

    Also type-checks every free-text ``Optional[str]`` field on
    ``Recommendation`` so every deserialization path shares one check
    instead of each caller repeating it (or, as round 4 did, repeating it
    for only 3 of the 6 such fields) -- purity_cache.py's
    ``_entry_from_json`` used to skip this entirely, so a non-string
    ``restated_property`` reached ``restated_property_or_none()`` and
    crashed far from the malformed-data site; a non-string ``file_path``
    still does, in ``_collect_finding_path_mentions``'s ``paths.add(...)``.
    Excludes ``impact``/``complexity`` (degrade via ``_triage_level``'s
    ``.get(..., -1)`` on a bad *value*, not a type check, but a non-string
    input still isn't covered here -- out of this round's scope) and
    ``severity``/``confidence`` (already enum-checked below/by the caller).
    """
    values = dict(raw)
    for field_name in (
        "suggested_action",
        "anchor",
        "restated_property",
        "purity_verdict_provenance",
        "file_path",
        "target_signature",
    ):
        value = values.get(field_name)
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"recommendation {field_name} must be a string or null"
            )
    confidence = values.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, str)
        or confidence not in RECOMMENDATION_CONFIDENCES
    ):
        raise ValueError(
            "recommendation confidence must be one of "
            f"{sorted(RECOMMENDATION_CONFIDENCES)!r} or null"
        )
    # Preserve the legacy absent/null representation instead of letting the
    # dataclass default reinterpret it as a fresh limited finding.
    values["confidence"] = confidence
    redirect = values.get("redirect")
    if redirect is not None:
        if not isinstance(redirect, Mapping) or set(redirect) != {
            "reason", "suggested_next"
        }:
            raise ValueError("recommendation redirect must be an object with both fields")
        reason = redirect["reason"]
        suggested_next = redirect["suggested_next"]
        if not isinstance(reason, str) or not isinstance(suggested_next, str):
            raise ValueError("recommendation redirect fields must be strings")
        values["redirect"] = Redirect(
            reason=reason,
            suggested_next=suggested_next,
        )
    return Recommendation(**values)


FINDING_DOMAIN_CODE_LOGIC = "code-logic"
FINDING_DOMAIN_DOCS = "docs"
FINDING_DOMAIN_UNIT_TEST = "unit-test"
FINDING_DOMAIN_UNKNOWN = "unknown"

FINDING_DOMAINS = frozenset(
    {
        FINDING_DOMAIN_CODE_LOGIC,
        FINDING_DOMAIN_DOCS,
        FINDING_DOMAIN_UNIT_TEST,
        FINDING_DOMAIN_UNKNOWN,
    }
)

CARRIED_RESOLUTION_OPEN = "open"
CARRIED_RESOLUTION_APPLIED = "applied"
CARRIED_RESOLUTION_BLOCKED = "blocked"
CARRIED_RESOLUTION_SKIPPED = "skipped"

_CARRIED_BODY_EXCERPT_CHARS = 280
_CARRIED_BLOCK_MAX_FINDINGS = 30


@dataclass(frozen=True)
class CarriedFinding:
    """One accumulated finding carried into later audit/apply prompts."""

    anchor: Optional[str]
    title: str
    severity: str
    body_excerpt: str
    resolution: str = CARRIED_RESOLUTION_OPEN
    resolution_reason: str = ""
    confidence: Literal["supported", "limited"] | None = None


# Severity for each review primitive. Tuned to match what the user
# would intuitively expect to fix first: a heuristic hint is low signal,
# a blocked dep is structural, the path-style mismatch implies the whole
# review is suspect. A single declared path that doesn't resolve is a
# pre-execution structural hint on an unstarted step (not a bug in landed
# code), and apply now offers a durable fix (move it to ``creates:``), so
# it sits at ``medium`` rather than ``high``.
_FILE_CHECK_MISSING_PARENT_SEV = "medium"
_FILE_CHECK_NEW_ON_DONE_SEV = "medium"
_HEURISTIC_HIT_SEV = "info"
_DEP_BLOCKED_SEV = "high"
_DEP_UNKNOWN_SEV = "critical"
_PATH_STYLE_SEV = "critical"

# Display order for the severity-count banner. Not a new severity scheme —
# these are exactly the canonical level strings the ``_*_SEV`` constants and
# ``_CLAUDE_SEVERITY_MAP`` already produce, sorted highest-urgency first so
# critical/high read before advisory levels in the banner line.
RECOMMENDATION_SEVERITY_ORDER = ("critical", "high", "medium", "nit", "info")
# ``low`` remains readable for saved reviews from before current producers
# folded low-priority findings into ``nit`` or ``info``.
RECOMMENDATION_SEVERITIES = frozenset((*RECOMMENDATION_SEVERITY_ORDER, "low"))
RECOMMENDATION_CONFIDENCES = frozenset({"supported", "limited"})
_SEVERITY_BANNER_ORDER = RECOMMENDATION_SEVERITY_ORDER


def _carried_severity_rank(severity: str) -> int:
    """Sort known severity levels highest-urgency first; unknowns last."""
    try:
        return _SEVERITY_BANNER_ORDER.index(severity.lower())
    except ValueError:
        return len(_SEVERITY_BANNER_ORDER)


def _carried_body_excerpt(body: str) -> str:
    if len(body) <= _CARRIED_BODY_EXCERPT_CHARS:
        return body
    return body[: _CARRIED_BODY_EXCERPT_CHARS - 1] + "…"


def assemble_carried_findings(
    recs: Iterable[Recommendation],
    *,
    resolution_by_id: Optional[Mapping[str, tuple[str, str]]] = None,
) -> list[CarriedFinding]:
    """Build the deterministic carry-forward view of accumulated findings."""
    resolutions = resolution_by_id if resolution_by_id is not None else {}
    carried = []
    for rec in recs:
        resolution, reason = resolutions.get(
            rec.id, (CARRIED_RESOLUTION_OPEN, "")
        )
        carried.append(
            CarriedFinding(
                anchor=rec.anchor,
                title=rec.title,
                severity=rec.severity,
                body_excerpt=_carried_body_excerpt(rec.body),
                resolution=resolution,
                resolution_reason=reason,
                confidence=rec.confidence,
            )
        )
    return sorted(
        carried,
        key=lambda c: (
            _carried_severity_rank(c.severity),
            c.anchor or "",
            c.title,
        ),
    )


_CLAUDE_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "medium",  # fold into medium — same as launcher's verdict line
    "NIT": "nit",
    "UNSPECIFIED": "info",
}

# Severity for completeness primitives. All advisory by design; the
# correctness gates own the critical/high band.
_BODY_COMPLETENESS_SEV = "medium"
_DETAIL_MISSING_ON_DISK_SEV = "medium"
_DETAIL_UNREFERENCED_ON_DISK_SEV = "medium"
_DETAIL_BODY_INCOMPLETE_SEV = "medium"
_FILES_COHERENCE_DRIFT_SEV = "info"
_FILES_COHERENCE_NIT_SEV = "nit"

# Severity for the per-step ``change_type`` alignment audit
# (:func:`check_test_strategy_alignment`). The consistency nudge is a
# soft info-level prompt to classify the rest of the plan; a detail-Tests
# contradiction and a ``non-code`` step that nonetheless declares
# production source are medium — the declared classification disagrees
# with the written artifact, but it's a pre-execution authoring signal,
# not a landed-code regression.
_TEST_STRATEGY_INCONSISTENT_SEV = "info"
_TEST_STRATEGY_CONTRADICTION_SEV = "medium"
_TEST_STRATEGY_NONCODE_FOOTPRINT_SEV = "medium"

# Near-miss tuning for files-coherence ``detail_only`` findings.
#
# A detail body legitimately backtick-cites many *context* files (inputs
# it reads, downstream consumers, anchors to verify against) that the
# step never modifies; ``step.files`` is the *edit* set, not the mention
# set. So "cited but not declared" is the normal case and flagging every
# such path is almost pure noise. We only flag a cited path when it
# *resembles* a declared one — a typo or a stale/moved path the author
# forgot to re-sync — and silently ignore the rest as context references.
#
# Resemblance is either an identical (non-generic) basename in a
# different directory (the canonical drift case:
# ``packages/web/Foo.tsx`` declared, ``apps/web/src/Foo.tsx`` cited) or
# a high full-path string similarity (catches a typo *inside* the
# basename, e.g. ``Fooo.tsx`` vs ``Foo.tsx``).
_NEAR_MISS_RATIO = 0.85

# Max differing basename characters for a rule-2 near-miss, absolute rather
# than a ratio (length-sensitive). Calibrated in TestNearestDeclaredMatch:
# known typos/renames measured 1-4, real distinct siblings 6-9.
_NEAR_MISS_BASENAME_GAP = 4

# Ubiquitous filenames that collide across unrelated directories, so a
# shared basename carries no drift signal on its own. These are excluded
# from the basename-match rule (they can still match via the high
# similarity ratio when the surrounding path is also close). A genuine
# typo on one of these can be endorsed/ignored normally; the cost of a
# rare missed flag is lower than re-flooding the report with sibling
# ``index.ts`` collisions.
_GENERIC_BASENAMES = frozenset(
    {
        "index.ts",
        "index.tsx",
        "index.js",
        "index.jsx",
        "index.mjs",
        "index.cjs",
        "__init__.py",
        "mod.rs",
        "lib.rs",
        "main.rs",
        "main.go",
        "main.py",
        "types.ts",
        "utils.ts",
        "constants.ts",
        "schema.ts",
        "config.ts",
        "readme.md",
    }
)
_LESSONS_MISSING_FILE_SEV = "medium"
_LESSONS_MISSING_ENTRY_SEV = "medium"

# Marker the body-completeness check honors: a literal HTML comment of the
# form ``<!-- completeness:skip <Section> -->`` suppresses the missing /
# placeholder finding for that section. Case-insensitive on the section
# name; whitespace tolerated on either side.
_BODY_SKIP_MARKER_RE = re.compile(
    r"<!--\s*completeness:skip\s+([A-Za-z][A-Za-z ]*?)\s*-->",
    re.IGNORECASE,
)

# Recognized placeholder shapes inside a body section. ``_(TODO)_`` is the
# wizard's seed marker; bare ``TODO`` / ``TBD`` (case-insensitive, whole word)
# catch hand-stubbed sections. Only ever matched against the *whole* stripped
# body (``_body_section_is_placeholder`` uses ``fullmatch``), so the string
# appearing inside real prose never trips, and a legitimate "none" answer
# (``N/A`` / ``None`` in a Deferred / Out-of-scope section) is NOT a placeholder.
_BODY_PLACEHOLDER_RE = re.compile(
    r"_\((?:TODO|TBD)\)_|^\s*(?:TODO|TBD)\s*$|^\s*\((?:TODO|TBD)\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class BodyCompletenessIssue:
    """One missing or placeholder section in the plan's prose body.

    ``kind`` is ``"missing"`` when the required H2 heading is absent
    entirely; ``"placeholder"`` when the heading is present but the
    section body is empty or matches a TODO marker. ``section`` is the
    canonical section name (matches ``create.PLAN_BODY_SECTIONS``).
    """

    kind: str  # "missing" | "placeholder"
    section: str
    details: str


@dataclass(frozen=True)
class DetailCoverageIssue:
    """One step whose detail file is out of sync with the frontmatter.

    ``kind``:
      - ``"missing_on_disk"``: ``step.detail`` is set but the file isn't
        present.
      - ``"unreferenced_on_disk"``: ``step.detail`` is *unset*, yet a
        detail file for the step's id is on disk (and unclaimed by any
        other step) — the pointer was never persisted, so the launcher
        won't load it.

    A step with no ``detail:`` declaration AND no on-disk file is not
    flagged — that's normal operations, not a coverage defect.
    """

    step_id: int
    kind: str  # "missing_on_disk" | "unreferenced_on_disk"
    detail_path: Optional[str]


@dataclass(frozen=True)
class DetailBodyIssue:
    """One missing or placeholder section in a step's detail file.

    Same kind taxonomy as :class:`BodyCompletenessIssue`; ``section`` is
    one of the seven required tokens (Summary / Table of Contents / Why
    / Files / Implementation / Tests / Acceptance). ``detail_path`` is
    repo-relative.
    """

    step_id: int
    kind: str  # "missing" | "placeholder"
    section: str
    detail_path: str


@dataclass(frozen=True)
class FilesCoherenceIssue:
    """Drift between a step's detail body and its declared ``files:``.

    ``kind`` is ``"detail_only"`` when the detail body cites a path that
    isn't in ``step.files`` *and looks like a near-miss of a declared
    path* (a typo or stale/moved path, not an arbitrary context
    citation) — see :func:`_nearest_declared_match`; ``"files_only"``
    when a path appears in ``step.files`` but isn't mentioned in the
    detail body (nit-severity, suppressed when *every* declared file is
    mentioned somewhere).

    ``near_match`` is the declared path the cited one resembles; set
    only for ``detail_only`` so the finding can say *"did you mean X?"*.
    """

    step_id: int
    kind: str  # "detail_only" | "files_only"
    path: str
    near_match: Optional[str] = None


@dataclass(frozen=True)
class LessonsCoverageIssue:
    """A done step without a corresponding entry in the lessons log.

    ``kind`` is ``"missing_file"`` when ``plan.lessons`` is set but the
    file doesn't exist (one finding per plan, not per step);
    ``"missing_entry"`` when the file exists but no line names this
    step's id.
    """

    step_id: Optional[int]  # None for the missing-file case
    kind: str  # "missing_file" | "missing_entry"
    lessons_path: str


@dataclass(frozen=True)
class PathStyleHint:
    """Plan-wide signal that declared file paths probably don't match repo root.

    Surfaced when ≥``_PATH_STYLE_MISMATCH_THRESHOLD`` of the plan's declared
    files resolve to ``MISSING_PARENT``. The cause is almost always a systemic
    prefix mismatch (plan authored against a different repo root) rather than
    individual broken paths.
    """

    missing_count: int
    total: int
    ratio: float
    examples: list[str]  # up to _PATH_STYLE_EXAMPLE_LIMIT representative offenders
    repo_root: Path


class ReviewError(Exception):
    """Raised for review-level problems: unknown step id, etc."""


def _reject_unmatched_plan_fence(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    if _fenced_code_spans(_split_frontmatter(text).body).unmatched_opening is not None:
        raise ReviewError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before reconciling this plan."
        )


def shell_review_invoker(prompt: str) -> tuple[int, str]:
    """Production invoker: capture ``claude -p`` stdout + exit code.

    Delegates to :func:`plan_tool.shell.claude_invoke`. The review
    pipeline needs the exit code (not just stdout) because the
    semantic-review section distinguishes "claude not on PATH" (exit 127
    → "skipped" note) from "claude exited non-zero" (different note) from
    "claude returned empty" (yet a third note).
    """
    return claude_invoke(prompt)


def shell_plan_audit_invoker(prompt: str) -> _PlanAuditInvocation:
    """Invoke one conceptual audit and retain its typed failure kind."""
    outcome: ClaudeInvokeOutcome = claude_invoke_outcome(prompt)
    return _PlanAuditInvocation(
        outcome.rc,
        outcome.stdout,
        failure_kind=(outcome.failure.kind if outcome.failure is not None else None),
    )


_PLAN_AUDIT_INVOKER_CAPABILITY = object()

# ``functools.wraps`` carries this capability to ordinary logging/telemetry
# wrappers without requiring them to remain identity-equal to this function.
setattr(shell_review_invoker, "plan_audit_invoker", shell_plan_audit_invoker)
setattr(
    shell_review_invoker,
    "plan_audit_invoker_capability",
    _PLAN_AUDIT_INVOKER_CAPABILITY,
)


def plan_audit_invoker_from_review_invoker(
    invoker: Invoker,
) -> PlanAuditInvoker:
    """Use a review invoker's optional typed audit capability."""
    if (
        getattr(invoker, "plan_audit_invoker_capability", None)
        is not _PLAN_AUDIT_INVOKER_CAPABILITY
    ):
        return invoker
    typed_invoker = getattr(invoker, "plan_audit_invoker", None)
    if callable(typed_invoker):
        return typed_invoker
    return invoker


def check_file_existence(plan: Plan, repo_root: Path) -> list[StepFileCheck]:
    """For each step, classify each declared file as OK / NEW / MISSING_PARENT.

    Both ``files`` (existing files the step modifies) and ``creates``
    (files the step brings into existence) are classified; ``creates``
    entries carry ``created=True`` so downstream finding logic can exempt
    them from the missing/doesn't-resolve warnings (a created file is
    *supposed* to be absent until the step runs).

    The classification is plan-wide, not per-step: directories that an
    earlier step's ``creates:`` entry will materialize are projected
    forward, so a later step's ``files:`` entry living under one of them
    downgrades from MISSING_PARENT to NEW rather than nagging about a path
    that is correct by plan design. Coverage is credited in plan-list order
    (positional), mirroring ``next_runnable_step``; no ``depends_on`` sort.
    """
    results: list[StepFileCheck] = []
    # Repo-relative directories earlier steps' ``creates:`` will bring into
    # existence (parents plus all ancestors). Pure posix-path math, no disk
    # access — plan paths are always posix.
    will_exist_dirs: set[PurePosixPath] = set()
    posix_root = PurePosixPath(".")
    for step in plan.steps:
        entries: list[FileCheck] = []
        for f, created in (
            *((f, False) for f in step.files),
            *((f, True) for f in step.creates),
        ):
            p = repo_root / f
            if p.exists():
                status = FileExistence.OK
            elif p.parent.exists():
                status = FileExistence.NEW
            else:
                status = FileExistence.MISSING_PARENT
            # Cross-step downgrade: a modified file (``created=False``) whose
            # parent directory an *earlier* step's ``creates:`` will produce
            # is NEW, not a suspect path. Created entries keep their on-disk
            # status — they're already exempt from warnings via ``created``.
            if (
                status == FileExistence.MISSING_PARENT
                and not created
                and PurePosixPath(f).parent in will_exist_dirs
            ):
                status = FileExistence.NEW
            entries.append(FileCheck(path=f, status=status, created=created))
        results.append(StepFileCheck(step_id=step.id, files=entries))
        # Fold this step's created files' parents + ancestors into the set
        # *after* classifying, so a step never credits its own ``files:`` —
        # only earlier-in-list steps do. All ``creates:`` count regardless of
        # their own on-disk status (a step that itself has a MISSING_PARENT
        # ``creates:`` still legitimately produces the directory). The ``.``
        # root carries no signal — a file directly under repo root already
        # classifies NEW because repo_root exists.
        for c in step.creates:
            created_parent = PurePosixPath(c).parent
            for ancestor in (created_parent, *created_parent.parents):
                if ancestor != posix_root:
                    will_exist_dirs.add(ancestor)
    return results


def _promote_missing_parents(
    file_checks: list[StepFileCheck],
) -> list[StepFileCheck]:
    """Treat MISSING_PARENT entries as NEW.

    Used when the caller passes ``--allow-missing-parent`` to acknowledge
    that the step legitimately creates files under a directory that
    doesn't exist yet. Promoting to NEW silences both the per-step
    MISSING_PARENT warning and the plan-wide path-style hint (which keys
    off MISSING_PARENT counts), while still letting NEW-on-DONE warnings
    fire if a DONE step's file never landed.
    """
    promoted: list[StepFileCheck] = []
    for sfc in file_checks:
        new_files = [
            FileCheck(
                path=fc.path,
                status=(
                    FileExistence.NEW
                    if fc.status == FileExistence.MISSING_PARENT
                    else fc.status
                ),
                created=fc.created,
            )
            for fc in sfc.files
        ]
        promoted.append(StepFileCheck(step_id=sfc.step_id, files=new_files))
    return promoted


def _derive_symbols(title: str) -> list[str]:
    """Pull 0+ candidate identifier tokens from a step title.

    Drops stopwords and <3-char tokens. Preserves original casing so the
    template ``class {cap}`` gets a sensible capitalization.
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", title)
    out: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        lo = t.lower()
        if len(lo) < 3 or lo in _TITLE_STOPWORDS or lo in seen:
            continue
        seen.add(lo)
        out.append(t)
    return out


def _derive_file_path_symbols(path: str) -> list[str]:
    """Pull conservative identifier candidates from a declared file path."""
    posix_path = PurePosixPath(path)
    pieces: list[str] = []
    for raw_part in posix_path.parts:
        part = raw_part
        if part in {"", ".", ".."}:
            continue
        if part == posix_path.name:
            part = posix_path.stem
        if not part:
            continue
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*", part):
            if token.lower() in _PATH_SYMBOL_STOPWORDS:
                continue
            pieces.append(token)
    return _derive_symbols(" ".join(pieces))


def _merge_candidate_symbols(
    existing: list[str], additions: Iterable[str]
) -> None:
    seen = {symbol.lower() for symbol in existing}
    for symbol in additions:
        key = symbol.lower()
        if key in seen:
            continue
        seen.add(key)
        existing.append(symbol)


def heuristic_already_done(
    plan: Plan,
    repo_root: Path,
    *,
    max_bytes: int = _MAX_HEURISTIC_BYTES,
    prose_min_hits: int = _PROSE_MIN_HITS,
) -> list[HeuristicHit]:
    """Flag non-done steps whose files already define the symbols the title implies.

    Skips steps already marked ``done``: the whole point of a done step is that
    its symbols should be present, so flagging them would be noise.

    Reads three extension categories with different rules:
      - code (``_CODE_EXTS``): substring patterns; flag on first match.
      - prose (``_PROSE_EXTS``): line-anchored markdown headers; flag only
        when ≥``prose_min_hits`` matches in the file.
      - config (``_CONFIG_EXTS``): JSON/TOML key/section substrings; flag
        on first match.

    Files with any other extension are skipped entirely — the cost of
    extending coverage is more false positives, and the spec calls out
    YAML and binary files as deferred.

    **Detail cross-check**: when ``step.detail`` is set and the referenced
    file exists, symbols derived from the title are filtered to those the
    detail body also names. The detail file is the step's design intent;
    a symbol the author didn't mention in the design doc is unlikely to
    be the one the step is "already done" about. Steps with no detail
    file (or a declared-but-missing one) fall through to the unfiltered
    behavior.
    """
    hits: list[HeuristicHit] = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        symbols = _derive_symbols(step.title)
        if not symbols:
            continue
        symbols = _filter_symbols_by_detail(
            symbols, step, repo_root, max_bytes=max_bytes
        )
        if not symbols:
            continue
        for f in step.files:
            path = repo_root / f
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext in _CODE_EXTS:
                patterns = _PATTERN_TEMPLATES
                line_anchored = False
                min_hits = 1
            elif ext in _PROSE_EXTS:
                patterns = _PROSE_PATTERN_TEMPLATES
                line_anchored = True
                min_hits = prose_min_hits
            elif ext in _CONFIG_EXTS:
                patterns = _CONFIG_PATTERN_TEMPLATES
                line_anchored = False
                min_hits = 1
            else:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
            except OSError:
                continue
            hit = _scan_for_heuristic_hit(
                text,
                symbols,
                patterns,
                line_anchored=line_anchored,
                min_hits=min_hits,
            )
            if hit is None:
                continue
            sym, needle = hit
            hits.append(
                HeuristicHit(
                    step_id=step.id,
                    file=f,
                    symbol=sym,
                    pattern=needle,
                )
            )
    return hits


def _filter_symbols_by_detail(
    symbols: list[str],
    step: Step,
    repo_root: Path,
    *,
    max_bytes: int,
) -> list[str]:
    """Drop title-derived symbols the step's detail body doesn't mention.

    Returns ``symbols`` unchanged when:
      - ``step.detail`` is None (no design intent to cross-check against);
      - the detail file path doesn't resolve to a file (declared but
        missing — fall through to the unfiltered behavior so the user
        doesn't lose all heuristic signal due to a stale pointer);
      - the detail file is unreadable (OSError → fall through).

    Otherwise returns the subset of ``symbols`` whose lowercase form
    appears as a substring in the detail body. Substring (not whole-token)
    is intentional: detail prose may name a symbol with various
    morphologies (``parser``, ``Parser``, ``parsers``, ``parsing``) and
    the cross-check is meant to be permissive — its job is to drop
    *clearly* unrelated symbols, not to enforce strict naming.

    A detail body that is present and readable but declares an
    unsupported format version raises ``DetailFormatError`` rather than
    falling through — this function reads and interprets the body's prose
    (the substring cross-check below), so it is a semantic reader and must
    refuse, unlike the missing-file/unreadable-file cases above.
    """
    if step.detail is None:
        return symbols
    detail_path = repo_root / step.detail
    if not detail_path.is_file():
        return symbols
    try:
        full_body = detail_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return symbols
    require_supported_detail_format_version(full_body, path=detail_path)
    body_lower = full_body[:max_bytes].lower()
    return [s for s in symbols if s.lower() in body_lower]


def _scan_for_heuristic_hit(
    text: str,
    symbols: list[str],
    patterns: tuple[str, ...],
    *,
    line_anchored: bool,
    min_hits: int,
) -> Optional[tuple[str, str]]:
    """Return the first matching ``(symbol, needle)`` once total hits ≥ min_hits.

    For ``min_hits == 1`` (code/config) this returns immediately on the first
    matching pattern, preserving today's iteration order so existing
    code-only hits are unchanged.

    For ``min_hits > 1`` (prose) this sweeps every (symbol, pattern) pair,
    accumulating occurrence counts until the threshold is met. The returned
    pair identifies the *first* match found — that's what gets surfaced in
    the report; the additional hits are only used to clear the threshold.
    """
    first_match: Optional[tuple[str, str]] = None
    total = 0
    for sym in symbols:
        token = sym.lower()
        cap = sym[0].upper() + sym[1:] if sym else sym
        for template in patterns:
            needle = template.format(token=token, cap=cap)
            count = _count_pattern_occurrences(
                text, needle, line_anchored=line_anchored
            )
            if count == 0:
                continue
            if first_match is None:
                first_match = (sym, needle)
            total += count
            if total >= min_hits:
                return first_match
    return None


def _count_pattern_occurrences(
    text: str, needle: str, *, line_anchored: bool
) -> int:
    """Count how many times ``needle`` appears in ``text`` as a whole token.

    Uses :func:`re.compile` with ``\\b`` word boundaries appended only
    where the needle's outer character is a word character — this keeps
    quoted/bracketed config patterns (``"parser"``, ``[parser]``) working
    while still rejecting substring bleed in code patterns
    (``def parser`` no longer hits ``def parser_setup``).

    With ``line_anchored=True`` the pattern is also anchored to the start
    of a line (multiline regex), preserving the prose-extension behavior
    that markdown body text doesn't trigger header-shaped patterns.
    """
    return len(_compile_pattern(needle, line_anchored=line_anchored).findall(text))


def _compile_pattern(needle: str, *, line_anchored: bool) -> "re.Pattern[str]":
    """Build the regex used by :func:`_count_pattern_occurrences`.

    Split out for direct testing of the boundary logic — the rule is
    "wrap with ``\\b`` only where the adjacent needle char is a word
    character", which is fiddly enough that it earns its own surface.

    Empty needle is mapped to a never-matching pattern. Today's call
    sites can't pass an empty string (templates always include a literal
    keyword), but ``re.compile("")`` would match every position and
    inflate counts catastrophically — guard against future callers.
    """
    if not needle:
        return re.compile(r"(?!)")
    parts: list[str] = []
    if line_anchored:
        parts.append("^")
    if _is_word_char(needle[0]):
        parts.append(r"\b")
    parts.append(re.escape(needle))
    if _is_word_char(needle[-1]):
        parts.append(r"\b")
    flags = re.MULTILINE if line_anchored else 0
    return re.compile("".join(parts), flags)


def _is_word_char(c: str) -> bool:
    """Match Python's ``re`` ``\\w`` for ASCII (alnum or underscore)."""
    return c.isalnum() or c == "_"


def validate_deps(plan: Plan) -> list[DepIssue]:
    """Flag dependencies on unknown steps.

    Plan schema validation already rejects unknown ``depends_on`` at parse
    time (and a committed step depending on a parked step is rejected there
    too), so this is a defensive backstop for any ``Plan`` reaching here
    without having gone through full validation.
    """
    issues: list[DepIssue] = []
    by_id = {s.id: s for s in plan.steps}
    for s in plan.steps:
        for dep in s.depends_on:
            target = by_id.get(dep)
            if target is None:
                issues.append(
                    DepIssue(step_id=s.id, depends_on=dep, reason="unknown")
                )
    return issues


def detect_path_style_mismatch(
    file_checks: list[StepFileCheck],
    repo_root: Path,
    *,
    threshold: float = _PATH_STYLE_MISMATCH_THRESHOLD,
    example_limit: int = _PATH_STYLE_EXAMPLE_LIMIT,
) -> Optional[PathStyleHint]:
    """Return a hint when ≥``threshold`` of declared files have MISSING_PARENT.

    Returns ``None`` when no files are declared anywhere in the plan, or when
    the mismatched ratio is below the threshold (meaning failures are
    plausibly per-step bugs, not a systemic prefix issue).
    """
    missing: list[str] = []
    total = 0
    for step_check in file_checks:
        for fc in step_check.files:
            # Created files are expected to have a missing parent until the
            # step lands the directory — they're not evidence of a systemic
            # prefix mismatch, so exclude them from the ratio entirely.
            if fc.created:
                continue
            total += 1
            if fc.status == FileExistence.MISSING_PARENT:
                missing.append(fc.path)
    if total == 0:
        return None
    ratio = len(missing) / total
    if ratio < threshold:
        return None
    return PathStyleHint(
        missing_count=len(missing),
        total=total,
        ratio=ratio,
        examples=missing[:example_limit],
        repo_root=repo_root,
    )


def _section_skip_markers(body: str) -> set[str]:
    """Return lowercase section names suppressed via the skip marker."""
    return {
        m.group(1).strip().lower()
        for m in _BODY_SKIP_MARKER_RE.finditer(body or "")
    }


def _body_section_is_empty(text: str) -> bool:
    """True when a section body is empty or whitespace-only."""
    return not text.strip()


def _body_section_is_placeholder(text: str) -> bool:
    """True when a section body is a recognized TODO marker only.

    Placeholder check fires only when the *entire* body matches the
    placeholder pattern (allowing surrounding whitespace) — sections
    that mix real prose with a stray ``TODO`` aren't flagged.
    """
    stripped = text.strip()
    if not stripped:
        return False
    return _BODY_PLACEHOLDER_RE.fullmatch(stripped) is not None


def check_body_completeness(
    plan_path: Path,
    *,
    required_sections: Optional[Sequence[str]] = None,
) -> list[BodyCompletenessIssue]:
    """Find missing or placeholder H2 sections in the plan body.

    Reads the plan file directly and parses its body (the part the
    schema parser ignores). Required-section list defaults to
    ``create.PLAN_BODY_SECTIONS``; pass ``required_sections`` to
    override (test fixtures use this).

    The skip marker (``<!-- completeness:skip <Section> -->``) is honored
    case-insensitively and suppresses both the missing and placeholder
    findings for the named section.

    Returns ``[]`` when the body has all required sections populated
    with non-placeholder content. Caller controls severity / display.
    """
    # Imported here to break a potential circular import at module
    # load: ``create.py`` imports from ``review`` only via type hints
    # historically; importing the constant lazily keeps the module
    # graph clean.
    from plan_tool.create import PLAN_BODY_SECTIONS

    required = tuple(required_sections or PLAN_BODY_SECTIONS)
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        split = _split_frontmatter(text)
    except Exception:
        # Plan with no frontmatter — schema validation would have
        # caught this already; completeness has nothing to add.
        return []

    sections = split_body_sections(split.body, ignore_fenced_code=True)
    skipped = _section_skip_markers(_excise_fenced_code(split.body))

    issues: list[BodyCompletenessIssue] = []
    for name in required:
        key = name.lower()
        if key in skipped:
            continue
        if key not in sections:
            issues.append(
                BodyCompletenessIssue(
                    kind="missing",
                    section=name,
                    details=f"required H2 section `## {name}` is absent from the plan body",
                )
            )
            continue
        body_text = sections[key]
        if _body_section_is_empty(body_text):
            issues.append(
                BodyCompletenessIssue(
                    kind="placeholder",
                    section=name,
                    details=f"`## {name}` is present but its body is empty",
                )
            )
        elif _body_section_is_placeholder(body_text):
            issues.append(
                BodyCompletenessIssue(
                    kind="placeholder",
                    section=name,
                    details=f"`## {name}` body is a `_(TODO)_` placeholder",
                )
            )
    return issues


def check_lessons_coverage(
    plan: Plan, repo_root: Path
) -> list[LessonsCoverageIssue]:
    """Verify each done step has an entry in the configured lessons log.

    No-ops when ``plan.lessons`` is unset or no step is ``done``.

    Two finding kinds:
      - ``missing_file`` (one finding total) when the lessons file
        doesn't exist on disk but the plan has done steps.
      - ``missing_entry`` (one per step) when the file exists but no
        ``step <id>:`` line names this step.
    """
    if plan.lessons is None:
        return []
    done_ids = [s.id for s in plan.steps if s.status == StepStatus.DONE]
    if not done_ids:
        return []

    lessons_path = repo_root / plan.lessons
    if not lessons_path.is_file():
        return [
            LessonsCoverageIssue(
                step_id=None,
                kind="missing_file",
                lessons_path=plan.lessons,
            )
        ]

    # Lazy import to avoid a launcher → review cycle on module load.
    from plan_tool.launcher import read_lessons_step_ids

    seen = read_lessons_step_ids(lessons_path)
    issues: list[LessonsCoverageIssue] = []
    for step_id in done_ids:
        if step_id not in seen:
            issues.append(
                LessonsCoverageIssue(
                    step_id=step_id,
                    kind="missing_entry",
                    lessons_path=plan.lessons,
                )
            )
    return issues


def _strip_relative_prefix(path: str) -> str:
    """Drop leading ``./`` / ``../`` segments from a cited path.

    ``PurePosixPath`` (see :func:`_normalize_paths`) collapses ``./`` but
    keeps ``..``, and a body may cite ``../DETAIL_FORMAT.md`` to show link
    depth from a subdirectory — the same file the step declares as
    ``DETAIL_FORMAT.md``.
    """
    parts = path.split("/")
    while parts and parts[0] in {".", ".."}:
        parts.pop(0)
    return "/".join(parts)


def _nearest_declared_match(
    cited: str, declared: Sequence[str]
) -> Optional[str]:
    """Return the declared path ``cited`` is a near-miss of, or ``None``.

    A near-miss is a cited path that *resembles* a declared one closely
    enough to be a typo or a stale/moved path the author forgot to
    re-sync — the genuine drift signal. A cited path that resembles no
    declared path is a context reference (a file the step reads but
    doesn't modify) and is intentionally *not* a match, so the caller
    drops it instead of emitting noise.

    Two ways to qualify, strongest first:

    1. **Identical basename, different directory** — and the basename
       isn't in :data:`_GENERIC_BASENAMES`. This is the canonical case
       (``packages/web/Foo.tsx`` declared, ``apps/web/src/Foo.tsx``
       cited): the file moved or the prefix is wrong.
    2. **High full-path similarity** *and* few differing basename
       characters (an absolute count, not a ratio — a ratio is
       length-sensitive and misclassifies short-basename typos; see the
       ``TestNearestDeclaredMatch`` cases and BUG_BACKLOG).

    When several declared paths qualify, the highest-scoring one wins so
    the finding points at the most likely intended target.
    """
    cited_base = cited.rsplit("/", 1)[-1].lower()
    best: Optional[str] = None
    best_score = 0.0
    for d in declared:
        if d == cited:
            continue
        ratio = SequenceMatcher(None, cited.lower(), d.lower()).ratio()
        d_base = d.rsplit("/", 1)[-1].lower()
        same_base = (
            d_base == cited_base and cited_base not in _GENERIC_BASENAMES
        )
        if not same_base:
            if ratio < _NEAR_MISS_RATIO:
                continue
            basename_matcher = SequenceMatcher(None, cited_base, d_base)
            matched_chars = sum(
                block.size for block in basename_matcher.get_matching_blocks()
            )
            basename_gap = len(cited_base) + len(d_base) - 2 * matched_chars
            if basename_gap > _NEAR_MISS_BASENAME_GAP:
                continue
        # Rank: a shared basename is the stronger signal, so bias it
        # above any ratio-only match while still ordering ties by ratio.
        score = ratio + (1.0 if same_base else 0.0)
        if score > best_score:
            best_score = score
            best = d
    return best


def _repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Repo-relative POSIX label for ``path``, falling back to its own POSIX
    form when it lies outside ``repo_root``. The single labeler for both the
    finding paths and :func:`_format_audit_detail_bundle`'s bundle listing."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(frozen=True)
class _ResolvedDetailBody:
    """A step's readable detail body plus the repo-relative path that labels
    findings against it — the ``detail:`` pointer when set, the canonical
    path when unset."""

    text: str
    rel_path: str


def _resolve_detail_body(
    plan: Optional[Plan],
    step: Step,
    repo_root: Path,
    max_bytes: int,
    *,
    plan_path: Optional[Path],
) -> Optional[_ResolvedDetailBody]:
    """Read the detail body a quality check should judge, or ``None`` to skip.

    One resolution rule for every deterministic check that reads a detail
    body, via :func:`plan_tool.detail_artifacts.resolve_detail_artifact`:
    the ``detail:`` pointer when set, the canonical path when unset. The set
    of steps this resolves therefore matches what
    :func:`_format_audit_detail_bundle` renders into the audit prompt and
    what :func:`audit_detail_bundle_status` classifies as detailed, so the
    deterministic findings and the prompt never disagree about which steps
    have a body.

    A **set** pointer is authoritative: a set-but-missing pointer never falls
    back to the canonical file, so :func:`check_detail_coverage`'s
    ``missing_on_disk`` diagnostic keeps its meaning.

    ``plan`` / ``plan_path`` are optional; without them the canonical path
    can't be derived, so resolution is pointer-only — the compatibility
    default for callers holding only a parsed :class:`Plan`.

    Raises ``DetailFormatError`` uncaught when a present, readable body
    declares an unsupported or malformed format version — every caller of
    this shared resolver inherits that refusal.
    """
    if plan is None or plan_path is None:
        if not step.detail:
            return None
        path = repo_root / step.detail
        if not path.is_file():
            return None
    else:
        resolution = resolve_detail_artifact(plan_path, plan, step, repo_root)
        if not resolution.on_disk:
            return None
        path = resolution.path
    try:
        full_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    require_supported_detail_format_version(full_text, path=path)
    return _ResolvedDetailBody(
        text=full_text[:max_bytes],
        rel_path=step.detail or _repo_relative_posix(path, repo_root),
    )


def check_files_coherence(
    plan: Plan,
    repo_root: Path,
    *,
    plan_path: Optional[Path] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[FilesCoherenceIssue]:
    """Compare each step's detail body to its declared footprint
    (``files:`` modified + ``creates:`` new).

    Two directions:
      - **detail_only**: a path cited in the detail body that isn't in
        the step's footprint *and is a near-miss of a declared path* (see
        :func:`_nearest_declared_match`). Most cited-but-undeclared
        paths are legitimate context references (files the step reads,
        not edits) and are dropped without a finding; only look-alikes —
        likely a typo or a stale/moved path the author forgot to
        re-sync — surface. Severity info.
      - **files_only**: a declared path not mentioned in the detail.
        Severity nit, and suppressed via short-circuit when *every*
        declared path is mentioned somewhere (the common-good case).

    Steps without a detail file on disk or with an empty footprint
    produce no findings. Path equality is exact-string match — no
    casing/whitespace normalization — so a renamed-but-not-resynced
    path surfaces as drift in both directions.

    Pass ``plan_path`` to judge a step whose ``detail:`` pointer is unset but
    whose canonical detail file is on disk (see :func:`_resolve_detail_body`);
    without it resolution stays pointer-only.

    Skips steps already marked ``done``: detail-vs-declared drift is a
    pre-execution authoring signal. Once the step is implemented the
    detail body has served its purpose, so coherence findings against it
    are moot — code-vs-plan divergence on a done step is the semantic
    review's and criteria-fulfillment's job, not this string check.
    """
    from plan_tool.detail import extract_filename_mentions, extract_path_mentions

    issues: list[FilesCoherenceIssue] = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        if not step.all_files:
            continue
        resolved = _resolve_detail_body(
            plan, step, repo_root, max_bytes, plan_path=plan_path
        )
        if resolved is None:
            continue
        body = resolved.text
        mentions = extract_path_mentions(body)
        # Both modified (``files``) and created (``creates``) paths are the
        # step's footprint, so coherence treats them uniformly.
        declared = set(step.all_files)
        recognized = declared | set(step.allowed_mentions)

        for cited in sorted(mentions - recognized):
            # An explicitly relative citation (``../DETAIL_FORMAT.md``, written
            # to illustrate link depth) names the same file as its resolved
            # form; comparing raw would read it as a stale sibling path and
            # emit a "did you mean" nit. See BUG_BACKLOG.
            cited_norm = _strip_relative_prefix(cited)
            if cited_norm in recognized:
                continue
            near = _nearest_declared_match(cited_norm, step.all_files)
            if near is None:
                # A context reference, not drift — drop it silently.
                continue
            issues.append(
                FilesCoherenceIssue(
                    step_id=step.id,
                    kind="detail_only",
                    path=cited,
                    near_match=near,
                )
            )

        # Short-circuit: only emit ``files_only`` nits when at least
        # one declared path is missing from the body. The full-mention
        # case is the common good outcome and shouldn't generate noise.
        #
        # A declared repo-root file (``BACKLOG.md``) can only ever be cited
        # bare, which the path-shaped regex can't see — so credit a declared
        # path whose basename is cited bare. Kept to this direction: feeding
        # bare tokens into the near-miss loop above would invent findings
        # against same-basename declarations. See BUG_BACKLOG.
        bare = extract_filename_mentions(body)
        mentioned = {_strip_relative_prefix(m) for m in mentions} | {
            d for d in declared if d.rsplit("/", 1)[-1] in bare
        }
        unmentioned = declared - mentioned
        if unmentioned and unmentioned != declared:
            # Mixed state: some declared paths cited, others not. Emit
            # a nit for each missing one — drift signal worth surfacing.
            for missing in sorted(unmentioned):
                issues.append(
                    FilesCoherenceIssue(
                        step_id=step.id,
                        kind="files_only",
                        path=missing,
                    )
                )
        elif unmentioned == declared:
            # No declared paths cited at all. Likely an analysis-style
            # detail that doesn't enumerate paths inline; emit a single
            # nit for the step rather than one-per-file.
            issues.append(
                FilesCoherenceIssue(
                    step_id=step.id,
                    kind="files_only",
                    path="(no declared files cited in detail body)",
                )
            )
    return issues


def _read_detail_body(
    step: Step,
    repo_root: Path,
    max_bytes: int,
    *,
    plan: Optional[Plan] = None,
    plan_path: Optional[Path] = None,
) -> str:
    """Return a step's on-disk detail body (``""`` when absent/unreadable).

    Thin wrapper over :func:`_resolve_detail_body` for callers that need only
    the text: supply ``plan`` and ``plan_path`` to include a step whose
    pointer is unset but whose canonical file is on disk. Reads plan-artifact
    markdown only.
    """
    resolved = _resolve_detail_body(
        plan, step, repo_root, max_bytes, plan_path=plan_path
    )
    return resolved.text if resolved is not None else ""


def _plan_body_sections(plan_path: Optional[Path]) -> dict[str, str]:
    """Return the plan body's H2 section map (``{}`` when no path/unreadable).

    Reads the plan markdown file, drops the frontmatter, and splits the prose
    below it (:func:`split_body_sections`). ``plan_path`` is optional so a
    caller holding only a parsed :class:`Plan` (no source path) still works —
    it just forgoes plan-level claim/deferred prose.

    An unmatched opening code fence is treated the same as an unreadable
    file (``{}``), not raised: this feeds advisory heuristic detectors
    reachable through both ``collect_deterministic_findings`` (guarded by
    its own top-level ``_reject_unmatched_plan_fence``) and
    ``collect_smell_findings`` (reachable from ``plan-tool validate`` and
    ``completeness-audit``, both of which promise never to raise on a
    malformed plan). Degrading to "no claim prose found" can under-inform a
    heuristic finding; raising here would crash those two live, no-raise
    call paths outright — the worse failure for an advisory check.
    """
    if plan_path is None:
        return {}
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        split = _split_frontmatter(text)
    except Exception:
        return {}
    if _fenced_code_spans(split.body).unmatched_opening is not None:
        return {}
    return split_body_sections(split.body, ignore_fenced_code=True)


@dataclass(frozen=True)
class PlanFootprint:
    """Both sides of the plan-consistency question, gathered in one pass.

    The *declared side* is what each step ships — its ``creates:``/``files:``
    paths (POSIX-normalized) and the identifier tokens those paths imply
    (:func:`_derive_file_path_symbols`). The *referenced side* is everything
    the plan mentions anywhere: path mentions in each step's detail body
    (:func:`plan_tool.detail.extract_path_mentions`) and the path/symbol tokens
    named in claim prose (``## Acceptance criteria`` / ``## Overview``, from both
    the plan body and each detail body). Per-step maps let a detector ask "is
    deliverable X referenced *outside* its declaring step?" without re-walking
    the plan; ``claim_paths`` / ``claim_symbols`` isolate the claim-prose tokens
    for a claim-vs-delivery check.

    Opens only plan and detail markdown (plan artifacts) — never a ``.py``/``.ts``
    source file — the same boundary :func:`check_files_coherence` respects.

    Paths are POSIX-normalized strings; symbols are lowercased identifier
    tokens. Both are matched exact-string after normalization (never free-text
    similarity — see :func:`detect_orphaned_deliverable`).
    """

    declared_paths: frozenset[str]
    declared_symbols: frozenset[str]
    declared_paths_by_step: Mapping[int, frozenset[str]]
    referenced_paths_by_step: Mapping[int, frozenset[str]]
    referenced_symbols_by_step: Mapping[int, frozenset[str]]
    claim_paths: frozenset[str]
    claim_symbols: frozenset[str]


def _normalize_paths(paths: Iterable[str]) -> set[str]:
    """POSIX-normalize path strings for exact-string comparison."""
    return {str(PurePosixPath(p)) for p in paths}


def _declared_footprint(
    plan: Plan,
) -> tuple[dict[int, frozenset[str]], dict[int, frozenset[str]]]:
    """Per-step declared paths and path-derived symbols. **Zero file I/O** —
    derives only from each step's ``all_files``. The declared side of
    :class:`PlanFootprint`, single-sourced so the full :func:`build_plan_footprint`
    and the declared-only ``claim-vs-delivery`` consumer can't drift.

    Returns ``(declared_paths_by_step, declared_symbols_by_step)``; callers union
    as needed (the by-step map is only consumed by the orphan check).
    """
    declared_paths_by_step: dict[int, frozenset[str]] = {}
    declared_symbols_by_step: dict[int, frozenset[str]] = {}
    for step in plan.steps:
        declared_paths_by_step[step.id] = frozenset(
            normalized
            for path in step.all_files
            if (normalized := normalize_declared_path(path))
        )
        step_symbols: set[str] = set()
        for f in step.all_files:
            step_symbols.update(s.lower() for s in _derive_file_path_symbols(f))
        declared_symbols_by_step[step.id] = frozenset(step_symbols)
    return declared_paths_by_step, declared_symbols_by_step


def _prose_symbols(text: str) -> set[str]:
    """Lowercased identifier tokens from prose (drops stopwords/short words)."""
    return {s.lower() for s in _derive_symbols(text)}


_DETAIL_CLAIM_SECTION_KEYS = ("acceptance", "overview")


def build_plan_footprint(
    plan: Plan,
    repo_root: Path,
    *,
    plan_path: Optional[Path] = None,
    plan_sections: Optional[dict[str, str]] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> PlanFootprint:
    """Gather the plan's declared deliverables and everything it references.

    One pass over the plan producing both sides of the consistency question so
    a detector (:func:`detect_orphaned_deliverable` here, ``claim-vs-delivery``
    in a later step) can key on declared paths/symbols rather than free English
    prose. See :class:`PlanFootprint` for the field contract.

    Reads only plan and detail **markdown** — never a source file. The
    referenced-symbol side scans the whole detail body (including fenced
    examples, but not just claim prose) so an in-scope consumer that names a
    deliverable by symbol still suppresses the orphan check; over-suppression
    is the intended conservative direction.
    """
    from plan_tool.detail import extract_path_mentions, parse_detail_file_sections

    detail_claim_keys = _DETAIL_CLAIM_SECTION_KEYS
    # Declared side (zero I/O) — single-sourced with the claim-vs-delivery consumer.
    declared_paths_by_step, declared_symbols_by_step = _declared_footprint(plan)
    referenced_paths_by_step: dict[int, frozenset[str]] = {}
    referenced_symbols_by_step: dict[int, frozenset[str]] = {}
    claim_paths: set[str] = set()
    claim_symbols: set[str] = set()

    for step in plan.steps:
        # Referenced side: path mentions (whole body) and symbol tokens.
        body = _read_detail_body(
            step, repo_root, max_bytes,
            plan=plan, plan_path=plan_path,
        )
        # A fenced sample remains an exact consumption citation. Keep it on the
        # conservative referenced side, but exclude it from claim prose below.
        referenced_paths_by_step[step.id] = frozenset(
            _normalize_paths(extract_path_mentions(body))
        )
        referenced_symbols_by_step[step.id] = frozenset(
            _prose_symbols(body)
        )

        # Claim prose from the detail's own acceptance-bearing sections.
        if body:
            sections = parse_detail_file_sections(_excise_fenced_code(body))
            for key in detail_claim_keys:
                text = sections.get(key, "")
                if not text:
                    continue
                claim_paths.update(_normalize_paths(extract_path_mentions(text)))
                claim_symbols.update(_prose_symbols(text))

    # Claim prose from the plan body's acceptance / overview sections. Accept a
    # caller-parsed ``plan_sections`` to avoid re-reading the plan file when the
    # caller already parsed it (the orphan detector needs the deferred sections).
    if plan_sections is None:
        plan_sections = _plan_body_sections(plan_path)
    for key in ("acceptance criteria", "overview"):
        text = _excise_fenced_code(plan_sections.get(key, ""))
        if not text:
            continue
        claim_paths.update(_normalize_paths(extract_path_mentions(text)))
        claim_symbols.update(_prose_symbols(text))

    def _union(maps: Iterable[frozenset[str]]) -> frozenset[str]:
        out: set[str] = set()
        for m in maps:
            out.update(m)
        return frozenset(out)

    return PlanFootprint(
        declared_paths=_union(declared_paths_by_step.values()),
        declared_symbols=_union(declared_symbols_by_step.values()),
        declared_paths_by_step=declared_paths_by_step,
        referenced_paths_by_step=referenced_paths_by_step,
        referenced_symbols_by_step=referenced_symbols_by_step,
        claim_paths=frozenset(claim_paths),
        claim_symbols=frozenset(claim_symbols),
    )


_REQUIRED_DETAIL_SECTION_NAMES = (
    ("summary", "Summary"),
    ("table", "Table of Contents"),
    ("why", "Why"),
    ("files", "Files"),
    ("implementation", "Implementation"),
    ("tests", "Tests"),
    ("acceptance", "Acceptance criteria"),
)


def check_detail_body_completeness(
    plan: Plan,
    repo_root: Path,
    *,
    plan_path: Optional[Path] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[DetailBodyIssue]:
    """For each step with a detail file on disk, verify seven non-empty H2s.

    Required tokens (matches ``detail._REQUIRED_H2_TOKENS``): summary,
    table, why, files, implementation, tests, acceptance. Each must be
    present AND have a non-empty, non-placeholder body. Summary and
    Table of Contents are reviewer-facing scaffolding required so a
    person auditing the file can orient before reading the body.

    Skips steps where the detail file is missing or unreadable —
    those are :class:`DetailCoverageIssue`s already (Step 2 /
    :func:`check_detail_coverage`); reporting both would double-count.

    Also skips steps already marked ``done``: a thin or incomplete detail
    body is a pre-execution authoring gap, moot once the step is
    implemented (the detail's job was to brief the run that already
    happened).

    Pass ``plan_path`` to judge a step whose ``detail:`` pointer is unset but
    whose canonical detail file is on disk (see :func:`_resolve_detail_body`);
    issues then carry the canonical repo-relative path.
    """
    # Lazy import to avoid pulling detail's heavy dependencies on
    # review module load.
    from plan_tool.detail import parse_detail_file_sections

    issues: list[DetailBodyIssue] = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        resolved = _resolve_detail_body(
            plan, step, repo_root, max_bytes, plan_path=plan_path
        )
        if resolved is None:
            continue
        detail_path = resolved.rel_path
        sections = parse_detail_file_sections(resolved.text)
        for token, display_name in _REQUIRED_DETAIL_SECTION_NAMES:
            if token not in sections:
                issues.append(
                    DetailBodyIssue(
                        step_id=step.id,
                        kind="missing",
                        section=display_name,
                        detail_path=detail_path,
                    )
                )
                continue
            section_body = sections[token]
            if _body_section_is_empty(section_body):
                issues.append(
                    DetailBodyIssue(
                        step_id=step.id,
                        kind="placeholder",
                        section=display_name,
                        detail_path=detail_path,
                    )
                )
            elif _body_section_is_placeholder(section_body):
                issues.append(
                    DetailBodyIssue(
                        step_id=step.id,
                        kind="placeholder",
                        section=display_name,
                        detail_path=detail_path,
                    )
                )
    return issues


def _planned_paths(plan: Plan) -> frozenset[str]:
    """Paths this plan's own steps will bring into existence. An ``## Input``
    anchor naming one is a forward dependency contract, not drift, so the
    existence check must not fire on it (see DATA_CONTRACT.md)."""
    return frozenset(c for s in plan.steps for c in s.creates)


def _sibling_roadmap_identity(
    plan: Plan, plan_path: Path, repo_root: Path
) -> tuple[Path, str] | None:
    """Return ordinary identity as None; uncertain evidence raises ValueError."""
    import yaml

    from plan_tool.pathutil import is_within
    from plan_tool.review_persistence import _resolve_source_seed_path
    from plan_tool.roadmap_artifacts import RoadmapArtifactError, parse_plans_artifact
    from plan_tool.roadmap_seed_state import (
        _marker_payload, _structural_state_path, locate_tracked_seed,
    )
    from plan_tool.roadmap_versions import load_accepted_version

    if not plan.source_seed:
        return None
    source = _resolve_source_seed_path(plan, repo_root)
    if source is None:
        raise ValueError("Source identity unavailable")
    text = source.read_text(encoding="utf-8")
    if text.startswith("> **Replaced**:"):
        _, separator, text = text.partition("\n\n")
        if not separator:
            raise ValueError("Incomplete replacement notice")
    metadata = {}
    if text.startswith("---"):
        try:
            metadata = yaml.safe_load(_split_frontmatter(text).frontmatter_yaml)
        except (yaml.YAMLError, ParseError) as exc:
            raise ValueError("Invalid seed metadata") from exc
        if not isinstance(metadata, dict):
            raise ValueError("Invalid seed metadata")
    marker = _marker_payload(text)
    if marker is None and "plan-tool-roadmap-seed-state:" in text:
        raise ValueError("Unrecognized seed lifecycle marker")
    if marker is not None and not is_within(repo_root / marker["state"], repo_root):
        raise ValueError("Seed state escapes repository")
    structural_state = _structural_state_path(source)
    if structural_state is not None and not is_within(structural_state, repo_root):
        raise ValueError("Seed state escapes repository")
    tracked = locate_tracked_seed(source, repo_root=repo_root)
    if marker is not None and tracked is None:
        raise ValueError("Tracked identity unavailable")
    slug, plan_id = metadata.get("roadmap"), metadata.get("plan_id")
    if tracked is not None:
        if ("roadmap" in metadata and slug != tracked.roadmap_slug) or (
            "plan_id" in metadata and plan_id != tracked.plan_id
        ):
            raise ValueError("Conflicting seed identity")
        slug, plan_id = tracked.roadmap_slug, tracked.plan_id
        owner = tracked.state_path.parent.resolve()
    elif "roadmap" in metadata or "plan_id" in metadata:
        if not isinstance(slug, str) or not isinstance(plan_id, str):
            raise ValueError("Incomplete seed identity")
        owner = (
            structural_state.parent.resolve()
            if structural_state is not None and structural_state.parent.parent.name == "roadmaps"
            else (plan_path.parent / "roadmaps" / slug).resolve()
        )
    elif "plan-tool-roadmap-seed-state:" in text or any(
        parent.parent.name == "roadmaps" for parent in source.parents
    ):
        raise ValueError("Unavailable tracked seed identity")
    else:
        return None
    if (
        not is_within(owner, repo_root)
        or owner.name != slug
        or owner.parent.name != "roadmaps"
    ):
        raise ValueError("Invalid roadmap owner")
    from plan_tool.roadmap_versions import (
        VERSION_ARTIFACT_KEYS, accepted_head_path, load_accepted_head,
        stored_artifact_path, stored_brief_path, stored_version_record_path,
    )

    plans_dir = owner.parent.parent
    if not is_within(accepted_head_path(plans_dir, slug), repo_root):
        raise ValueError("Accepted head escapes repository")
    head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    if head is not None:
        members = [
            stored_version_record_path(plans_dir, slug, head.version_id),
            stored_brief_path(plans_dir, slug, head.version_id),
            *(stored_artifact_path(plans_dir, slug, head.version_id, key)
              for key in VERSION_ARTIFACT_KEYS),
        ]
        if any(not is_within(member, repo_root) for member in members):
            raise ValueError("Accepted evidence escapes repository")
    accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if accepted is None:
        raise ValueError("Accepted roadmap unavailable")
    try:
        artifact = parse_plans_artifact(accepted.artifact_bytes[3].decode("utf-8"))
    except RoadmapArtifactError as exc:
        raise ValueError("Invalid accepted roadmap") from exc
    if not any(row.id == plan_id for row in artifact.plans):
        raise ValueError("Seed is absent from accepted roadmap")
    return owner, slug


def _eligible_planned_paths(
    plan: Plan, plan_path: Path, repo_root: Path
) -> frozenset[str]:
    """Combine own creates with repository-contained, eligible registered promises."""
    from plan_tool.locator import (
        ManifestError, default_manifest_path, load_manifest_plan_paths,
    )
    from plan_tool.parser import ValidationError
    from plan_tool.pathutil import is_within

    own = _planned_paths(plan)
    try:
        identity = _sibling_roadmap_identity(plan, plan_path, repo_root)
        manifest = default_manifest_path(repo_root)
        if manifest.is_file() and not isinstance(
            json.loads(manifest.read_text(encoding="utf-8")), dict
        ):
            return own
        candidates = load_manifest_plan_paths(repo_root)
    except (OSError, UnicodeError, ValueError, ManifestError):
        return own
    selected = set(own)
    for candidate in dict.fromkeys(candidates):
        if candidate == plan_path.resolve() or not is_within(candidate, repo_root):
            continue
        try:
            sibling = parse_plan(candidate)
            if identity is not None and (
                _sibling_roadmap_identity(sibling, candidate, repo_root) != identity
            ):
                continue
        except (OSError, UnicodeError, ValueError, ParseError, ValidationError):
            continue
        selected.update(
            path for path in _planned_paths(sibling)
            if normalize_declared_path(path)
            and is_within(repo_root / normalize_declared_path(path), repo_root)
        )
    return frozenset(selected)


def check_plan_input_contract_references(
    plan: Plan, plan_path: Path, repo_root: Path
) -> list[object]:
    """Validate the *plan body*'s optional ``## Input`` contract references.

    The plan-altitude half of :func:`check_input_contract_references`, split
    out so the completeness battery can address it apart from the per-step
    detail loop below — the two read different artifacts.
    """
    from plan_tool import data_contract as contract

    try:
        split = _split_frontmatter(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if split is None:
        return []
    try:
        plan_rel = (
            plan_path.resolve().relative_to(repo_root.resolve()).as_posix()
        )
    except ValueError:
        plan_rel = str(plan_path)
    return list(
        contract.check_input_contract_references(
            split.body,
            repo_root,
            location=f"{plan_rel}:## Input",
            path=plan_rel,
            planned_paths=_eligible_planned_paths(plan, plan_path, repo_root),
        )
    )


def check_step_input_contract_references(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    *,
    step_filter: Optional[int] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[object]:
    """Validate each step *detail body*'s optional ``## Input`` references.

    Bodies resolve through :func:`_resolve_detail_body`, so a step whose
    ``detail:`` pointer is unset but whose canonical file is on disk is
    validated too — labeled with that canonical repo-relative path.

    A read-only sweep over every step's own current on-disk content, so all
    steps share one fallback-walk cache — see BUG_BACKLOG for why that
    sharing is scoped to this one sweep rather than across separate calls.
    """
    from plan_tool import data_contract as contract

    planned_paths = _eligible_planned_paths(plan, plan_path, repo_root)
    tree_box: list[tuple[str, ...]] = []

    def tree_provider() -> tuple[str, ...]:
        if not tree_box:
            tree_box.append(contract._walk_anchor_search_tree(repo_root))
        return tree_box[0]

    issues: list[object] = []
    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        if step.status == StepStatus.DONE:
            continue
        resolved = _resolve_detail_body(
            plan, step, repo_root, max_bytes, plan_path=plan_path
        )
        if resolved is None:
            continue
        issues.extend(
            contract.check_input_contract_references(
                resolved.text,
                repo_root,
                location=f"{resolved.rel_path}:## Input",
                step_id=step.id,
                path=resolved.rel_path,
                planned_paths=planned_paths,
                tree_provider=tree_provider,
            )
        )
    return issues


def check_input_contract_references(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    *,
    step_filter: Optional[int] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[object]:
    """Validate optional plan/detail ``## Input`` contract references.

    Both arms in one call, plan body first — the shape the reconcile/review
    lane (:func:`collect_deterministic_findings`) wants. The completeness
    battery dispatches the two arms separately through
    :data:`INPUT_CONTRACT_DETECTORS`. A ``step_filter`` scopes the audit to one
    step, which drops the plan-altitude arm.
    """
    issues: list[object] = []
    if step_filter is None:
        issues.extend(
            check_plan_input_contract_references(plan, plan_path, repo_root)
        )
    issues.extend(
        check_step_input_contract_references(
            plan,
            plan_path,
            repo_root,
            step_filter=step_filter,
            max_bytes=max_bytes,
        )
    )
    return issues


def check_detail_coverage(
    plan: Plan, plan_path: Path, repo_root: Path
) -> list[DetailCoverageIssue]:
    """Flag steps whose detail file is out of sync with the frontmatter.

    Two kinds:
      - ``missing_on_disk``: ``step.detail`` is set but the file isn't
        present under ``repo_root``. Severity medium.
      - ``unreferenced_on_disk``: ``step.detail`` is *unset*, yet a detail
        file for the step's id (``plan-details/<slug>/<NN>-*.md``) is on
        disk and unclaimed by any other step's pointer — the reference was
        never persisted (e.g. a split that renumbered an unpointed step),
        so the launcher silently won't load it. Severity medium.

    A step with no ``detail:`` field AND no on-disk file is *not* flagged —
    authoring detail files is a normal part of operations, not a defect.

    Skips steps already marked ``done``: the detail file is the design
    intent fed to the step's subprocess before it runs. Once the step is
    implemented that intent has served its purpose, so a
    declared-but-missing detail file is moot — flagging it would be noise.
    """
    issues: list[DetailCoverageIssue] = []
    # Filenames another step's pointer already owns — never report those as
    # an unreferenced orphan for a *different* step.
    claimed = {
        Path(s.detail).name for s in plan.steps if s.detail is not None
    }
    bundle_dir = (
        plan_path.parent / "plan-details" / slug_from_filename(plan_path)
    )
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        if step.detail is None:
            # Pointer never persisted: surface any on-disk detail file for
            # this step's id so the operator can reattach it (``plan-tool
            # detail --step N`` adopts the canonical one). Mirrors the
            # ``plan-details/<slug>/`` convention, duplicated here on
            # purpose: ``detail_artifacts`` owns the canonical *file*
            # derivation (``derive_detail_path``) but exposes no
            # bundle-directory helper, and this needs the directory before
            # any step is in hand.
            if not bundle_dir.is_dir():
                continue
            orphans = [
                p
                for p in sorted(bundle_dir.glob(f"{step.id:02d}-*.md"))
                if p.is_file() and p.name not in claimed
            ]
            if orphans:
                rel = _repo_relative_posix(orphans[0], repo_root)
                issues.append(
                    DetailCoverageIssue(
                        step_id=step.id,
                        kind="unreferenced_on_disk",
                        detail_path=rel,
                    )
                )
            continue
        path = repo_root / step.detail
        if not path.is_file():
            issues.append(
                DetailCoverageIssue(
                    step_id=step.id,
                    kind="missing_on_disk",
                    detail_path=step.detail,
                )
            )
    return issues


def _is_scannable_path(path: str) -> bool:
    """True when ``heuristic_already_done`` would open ``path`` — i.e. its
    extension is in :data:`_SCANNABLE_EXTS` (code/prose/config).

    An un-hit file with an *unscannable* extension (``.yaml``, ``.sh``, …) was
    never opened, so its lack of a hit says nothing about built-ness; the
    code-reveals-a-split detector must not count it as un-built evidence (doing
    so would flag a fully-built step whose only un-hit declared file is
    unscannable).
    """
    return PurePosixPath(path).suffix.lower() in _SCANNABLE_EXTS


# Colocated Vitest/Jest basenames (``foo.test.ts``, ``foo.spec.tsx``, …).
_COLOCATED_TEST_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".test.mjs",
    ".test.cjs",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.mjs",
    ".spec.cjs",
)


def _is_test_code_path(path: str) -> bool:
    """True when ``path`` is test code rather than production source.

    Used by :func:`check_test_strategy_alignment`'s non-code footprint
    check and the launcher test-authoring gate: ``non-code`` means
    "changes no *production* code", so test files never contradict the
    classification / fail the gate. Recognized shapes:

    - a ``tests`` / ``test`` / ``__tests__`` directory anywhere above the
      basename
    - a ``test_*.py`` basename or ``conftest.py``
    - colocated Vitest/Jest basenames (``*.test.ts(x)``, ``*.spec.js``, …)
    """
    p = PurePosixPath(path)
    if any(part in ("tests", "test", "__tests__") for part in p.parts[:-1]):
        return True
    name = p.name
    if name.startswith("test_") or name == "conftest.py":
        return True
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in _COLOCATED_TEST_SUFFIXES)


# Prose phrases for :func:`classify_finding_domain` when no path anchor exists.
_DOCS_DOMAIN_PROSE_PHRASES = (
    "detail body",
    "declared files cited",
    "no declared files cited",
    "files: footprint",
    "section heading",
    "format.md",
)
_CODE_LOGIC_DOMAIN_PROSE_PHRASES = (
    "call site",
    "invoker",
    "merge_bridge",
    "passthrough",
    "repo_root",
    "shell-out",
    "shell out",
)

# Keep this set narrow; advisory false positives can hide plan obligations.
_BARE_MECHANISM_PHRASES = (
    "attachment",
    "carrier",
    "dependency ordering",
    "dependency rewrite",
    "dependency rewiring",
    "parser arrangement",
    "fixture shape",
    "rewrite dependency",
    "rewire dependency",
    "serializer",
    "telemetry value",
)
_BARE_MECHANISM_REQUEST_RE = re.compile(
    r"\b(?:add|attach|choose|define|introduce|require|rewrite|select|specify|"
    r"use|wire)\b"
)
_BARE_MECHANISM_PROTECTED_PHRASES = (
    "acceptance criterion",
    "acceptance criteria",
    "acceptance result",
    "acceptance results",
    "property",
    "properties",
    "ownership boundary",
    "ownership boundaries",
    "safety guarantee",
    "safety guarantees",
    "ordering rule",
    "ordering rules",
    "route",
    "routes",
)
_BARE_MECHANISM_CONTRACT_RE = re.compile(
    r"\b(?:compatibility|safety|ordering|ownership|bypass)\s+contract\b|"
    r"\b(?:observable|externally observable)\b[^.\n]{0,80}\b"
    r"(?:compatibility|safety|ordering|ownership|bypass)\b"
)


def _collect_finding_path_mentions(rec: Recommendation) -> set[str]:
    """Backtick path tokens from a finding's text fields plus ``file_path``."""
    from plan_tool.detail import extract_filename_mentions, extract_path_mentions

    parts = [rec.title, rec.body]
    if rec.suggested_action:
        parts.append(rec.suggested_action)
    text = "\n".join(parts)
    paths = set(extract_path_mentions(text))
    paths.update(extract_filename_mentions(text))
    if rec.file_path:
        paths.add(rec.file_path)
    return paths


_STEP_DETAIL_FILENAME_RE = re.compile(r"^\d+-")


def _is_plan_authoring_path(path: str) -> bool:
    """True when ``path`` is a step detail file, not reference documentation.

    Narrower than "anywhere under plan-details/": saved reports, grounding,
    and concept-tree artifacts also live under that segment
    (``completeness_report.py``, ``grounding.py``, ``concept_tree.py``) and
    are genuinely reporting output, not the plan/detail content under audit
    -- ``TestClassifyFindingDomain.test_classify_finding_domain_docs_
    implementation_plans_path`` pins a ``plan-details/<slug>/reports/*.json``
    path classifying ``"docs"``. Only a numbered step file
    (:func:`~plan_tool.detail_artifacts.derive_detail_path`:
    ``plan-details/<slug>/<NN>-<slug>.md``) is excluded: a finding
    citing one is about the plan/detail bundle under audit -- the subject of
    a conceptual finding, not supporting docs. The plan file itself has no
    fixed path convention across repos and isn't detected here; a finding
    that cites only the plan file still falls back to prose-phrase signals
    or ``"unknown"``.
    """
    p = PurePosixPath(path)
    parts = p.parts
    if "plan-details" not in parts or "reports" in parts:
        return False
    return p.suffix.lower() == ".md" and bool(_STEP_DETAIL_FILENAME_RE.match(p.stem))


def _path_finding_domain_signal(path: str) -> Optional[str]:
    """Map one path token to a domain signal, or ``None`` when unclassified."""
    if _is_test_code_path(path):
        return FINDING_DOMAIN_UNIT_TEST
    if _is_plan_authoring_path(path):
        return None
    p = PurePosixPath(path)
    parts = p.parts[1:] if p.parts[:1] == ("/",) else p.parts
    ext = p.suffix.lower()
    if ext in _PROSE_EXTS or parts[:1] == ("docs",):
        return FINDING_DOMAIN_DOCS
    if ext in _CODE_EXTS:
        return FINDING_DOMAIN_CODE_LOGIC
    return None


def _prose_matches_phrases(text: str, phrases: tuple[str, ...]) -> bool:
    """Word-boundary phrase match -- a bare substring check would also fire
    inside an unrelated compound (``implementation`` inside
    ``implementation-plans``, this repo's own plan/detail directory name)."""
    lower = text.lower()
    return any(
        re.search(rf"\b{re.escape(phrase)}\b", lower) is not None
        for phrase in phrases
    )


def classify_likely_bare_mechanism(rec: Recommendation) -> bool:
    """Whether persisted text likely requests a detail-owned delivery choice.

    Explicit property, route, and observable-contract language wins over a
    mechanism phrase. This is an advisory-only, text-only classifier.
    """
    parts = [rec.title, rec.body]
    if rec.suggested_action:
        parts.append(rec.suggested_action)
    text = "\n".join(parts)
    lower = text.lower()

    if (
        _prose_matches_phrases(text, _BARE_MECHANISM_PROTECTED_PHRASES)
        or _BARE_MECHANISM_CONTRACT_RE.search(lower) is not None
    ):
        return False

    return (
        _BARE_MECHANISM_REQUEST_RE.search(lower) is not None
        and _prose_matches_phrases(text, _BARE_MECHANISM_PHRASES)
    )


def classify_finding_domain(rec: Recommendation) -> str:
    """Classify conceptual-audit finding prose into a closed domain label.

    Matched-signal precedence: code-logic > unit-test > docs > unknown.
    Pure and deterministic — no filesystem or plan parse. The label only
    demotes a medium-severity finding from blocking when it resolves
    ``"docs"`` — ``"code-logic"``/``"unit-test"``/``"unknown"`` all block, at
    both audit stages. See ``convergence.is_blocking_finding`` and
    ``convergence.is_blocking_impact`` for the blocking policy that consumes
    this label, and docs/how-to/pipeline/audit.md's "Conceptual bar set" and "Calibrated
    impact-aware convergence" for the full rationale.
    """
    has_code_logic = False
    has_unit_test = False
    has_docs = False

    for path in _collect_finding_path_mentions(rec):
        signal = _path_finding_domain_signal(path)
        if signal == FINDING_DOMAIN_CODE_LOGIC:
            has_code_logic = True
        elif signal == FINDING_DOMAIN_UNIT_TEST:
            has_unit_test = True
        elif signal == FINDING_DOMAIN_DOCS:
            has_docs = True

    if rec.source == "test-strategy":
        has_unit_test = True

    prose_parts = [rec.title, rec.body]
    if rec.suggested_action:
        prose_parts.append(rec.suggested_action)
    prose = "\n".join(prose_parts)
    if _prose_matches_phrases(prose, _DOCS_DOMAIN_PROSE_PHRASES):
        has_docs = True
    if _prose_matches_phrases(prose, _CODE_LOGIC_DOMAIN_PROSE_PHRASES):
        has_code_logic = True

    if has_code_logic:
        return FINDING_DOMAIN_CODE_LOGIC
    if has_unit_test:
        return FINDING_DOMAIN_UNIT_TEST
    if has_docs:
        return FINDING_DOMAIN_DOCS
    return FINDING_DOMAIN_UNKNOWN


def check_test_strategy_alignment(plan: Plan) -> list[Recommendation]:
    """Audit each step's ``change_type`` classification against the
    written artifacts, emitting ``source="test-strategy"`` findings.

    Opt-in per plan: a plan whose steps carry no ``change_type`` produces
    no findings (legacy plans predate the classification). Two shapes:

      - **(a) Consistency nudge** (plan-level, info): some steps declare a
        ``change_type`` while siblings leave it unset. One finding naming
        the unclassified ids — classify the rest (or none) so the
        classification is unambiguous plan-wide (it drives the
        test-authoring gate and the MIXED-STEP granularity split).
      - **(b) Non-code footprint contradiction** (per-step, medium): a
        ``non-code`` step whose ``files``/``creates`` include a production
        source path (suffix in :data:`_CODE_EXTS`, excluding test code —
        see :func:`_is_test_code_path`). Test-authoring
        changes no production code, so a tests-only footprint is exactly
        what ``non-code`` describes; only non-test source contradicts the
        classification.

    Every finding carries ``source="test-strategy"``, which is *absent*
    from :data:`APPLY_ELIGIBLE_SOURCES`, so each routes to
    ``deferred_kind() == "diagnostic"`` (report-only — ``apply_finding``
    can't author a detail file, rewrite ``step.files``, or re-classify a
    step).

    Neither shape opens a detail file: both read plan structure only. The
    body-reading loop this check once carried went with the withdrawn
    per-``change_type`` test-ordering contract (see ``CLAUDE.md``).
    """
    classified = [s for s in plan.steps if s.change_type is not None]
    if not classified:
        return []

    recs: list[Recommendation] = []

    # (a) Consistency nudge — plan-level, info. One finding only when the
    # plan is genuinely mixed (both classified and unclassified steps).
    unclassified_ids = sorted(s.id for s in plan.steps if s.change_type is None)
    if unclassified_ids:
        id_list = ", ".join(str(i) for i in unclassified_ids)
        fingerprint = "consistency:" + ",".join(str(i) for i in unclassified_ids)
        recs.append(
            Recommendation(
                id=_make_rec_id(None, "test-strategy", fingerprint),
                source="test-strategy",
                severity=_TEST_STRATEGY_INCONSISTENT_SEV,
                step_id=None,
                title="Some steps declare `change_type`, others don't",
                body=(
                    f"{len(classified)} step(s) declare a `change_type`, but "
                    f"step(s) {id_list} leave it unset. Classify every step "
                    "(or none) so the classification is unambiguous "
                    "plan-wide — it drives the test-authoring gate and "
                    "the MIXED-STEP granularity split."
                ),
                suggested_action=(
                    f"add a `change_type` to step(s) {id_list}, or remove "
                    "it from every step — keep the plan all-or-nothing"
                ),
            )
        )

    # (b) Non-code footprint contradiction — per-step, medium. Test code
    # is exempt: ``non-code`` means "changes no production code", and a
    # tests-only footprint (test-authoring steps) satisfies that.
    for step in plan.steps:
        if step.change_type != ChangeType.NON_CODE:
            continue
        offending = sorted(
            f
            for f in step.all_files
            if PurePosixPath(f).suffix.lower() in _CODE_EXTS
            and not _is_test_code_path(f)
        )
        if not offending:
            continue
        paths_str = ", ".join(f"`{p}`" for p in offending)
        fingerprint = f"noncode-footprint:{step.id}:" + ",".join(offending)
        recs.append(
            Recommendation(
                id=_make_rec_id(step.id, "test-strategy", fingerprint),
                source="test-strategy",
                severity=_TEST_STRATEGY_NONCODE_FOOTPRINT_SEV,
                step_id=step.id,
                title=(
                    f"Step {step.id}: `non-code` step declares production "
                    "source path(s)"
                ),
                body=(
                    f"Step {step.id} is classified `non-code` (changes no "
                    f"production code), but its footprint includes {paths_str}. "
                    "Either the classification is wrong (it's a code step) or "
                    "the path doesn't belong in this step."
                ),
                suggested_action=(
                    f"re-classify step {step.id} as a code step, or move "
                    f"the production path(s) ({paths_str}) to the step "
                    "that owns them"
                ),
            )
        )

    return recs


# --- Semantic smell layer (feature-ref hygiene + suppression/self-ref) ------
#
# The semantic layer above the step-1 ``features`` types. Its sources
# (``feature-ref`` / ``suppression-shape`` / ``self-referential``) are all
# deliberately absent from :data:`APPLY_ELIGIBLE_SOURCES`, so
# :func:`is_apply_eligible` is ``False``, ``triage_reason`` routes them to the
# generic "structural diagnostic" text, and ``apply_finding`` never touches
# them; none are wired into :func:`collect_deterministic_findings`, which feeds
# the ``--iterate`` apply loop. They are fanned out by
# :func:`collect_smell_findings`. Most stay ``info`` (purely advisory); the
# elevated ones (``suppression-shape``, ``intent-presence``) emit ``medium``,
# and the completeness battery partitions every source in
# :data:`SELF_CONSISTENCY_SOURCES` out of the advisory ``smell_recs`` bucket
# onto the blocking-capable ``self_consistency_recs`` bucket (see
# ``cli/completeness_phases.py``).

# Single-source the suppression-shape source token so the detector here and the
# completeness-side partition key on one symbol.
SUPPRESSION_SHAPE_SOURCE = "suppression-shape"

# Anchored kebab-case predicate for a registry feature id: lowercase
# alphanumeric tokens joined by single hyphens. Written locally rather than
# reusing ``locator.slug_from_filename`` (a slug *producer*, not a *validator*).
_FEATURE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Trip predicate for the suppression-shape detector: a suppression *verb*
# (group 1) governing a gate-*object* noun within a short same-line window.
# Verb→object intent, not a bare keyword — precision matters because the plan
# authoring this feature is itself in the scanned corpus.
_SUPPRESSION_INTENT_RE = re.compile(
    r"\b(suppress|downgrade|bypass|exempt|silence|disable)\w*\b"
    r".{0,30}?"
    r"\b(?:gates?|checks?|findings?|severit(?:y|ies)|audits?)\b",
    re.IGNORECASE,
)

# How far back (chars) of the text *preceding* a suppression verb the
# non-trip guard scans. Looking only behind the verb keeps the match's own
# gate-object (always *after* the verb) out of the window, so a ``finding``
# object never excuses itself via the ``find`` detect-verb token.
_SUPPRESSION_LOOKBACK = 160

# Non-trip guard: excuse a suppression match when its lookback window shows
# the suppression is being *reasoned over* rather than *performed* — either
# (a) a class-of-units reference (a unit noun governing a ``that/which/whose``
# relative clause: "a step that…", "a step/feature whose…", "the detector
# that…", "steps that suppress…"), or (b) a detect/flag verb marking a
# deliverable whose action is to *detect* suppression, not perform it
# ("detect_suppression_shape", "catches the …", "surfaced").
_SUPPRESSION_REASONING_RE = re.compile(
    r"\b(?:steps?|features?|detectors?|units?|plans?)\b[^.\n]{0,20}?"
    r"\b(?:that|which|whose)\b"
    r"|"
    r"\b(?:detect|flag|catch|identif|surfac|find)\w*\b",
    re.IGNORECASE,
)

# (c) An explicit deliberate-design statement — a human decision to review, not
# a lexical blocker that should force prose evasion. Matched against the
# *current sentence only*, unlike (a)/(b): those describe the class of thing
# being discussed and read naturally across a sentence boundary, whereas "this
# was deliberate" excuses a specific claim. Scanned over the whole lookback it
# would let an unrelated "We deliberately keep the run log terse." excuse a
# genuine suppression in the very next sentence.
_DELIBERATE_DESIGN_RE = re.compile(
    r"\b(?:we|i|this\s+(?:step|design|change|implementation)|"
    r"the\s+(?:design|decision|policy|contract))\b[^.\n]{0,100}?"
    r"\b(?:deliberately|intentionally|by\s+design)\b",
    re.IGNORECASE,
)


def _summary_and_why_text(body: str) -> str:
    """Return the concatenated ``## Summary`` and ``## Why`` section bodies.

    The suppression detector scans only these two sections of a detail file
    (plus the step title): the motivating ``type_impure`` stated its
    suppressing purpose in its rationale, not its anodyne title, so a
    title-only scan has near-zero recall. Shared with the tests.

    An unmatched opening fence falls back to scanning the *whole* raw body
    instead of the fence-stripped Summary/Why split: with a real ``## Why``
    admission sitting after the stray fence, ``split_body_sections`` would
    read it as fenced and excise it to EOF, silently defeating the exact
    audit this feeds. Scanning more text than usual is the safe direction
    here — a false positive is a reviewable finding, a false negative is
    the suppression getting through unnoticed.
    """
    if _fenced_code_spans(body).unmatched_opening is not None:
        return body
    sections = split_body_sections(body, strip_fenced_code=True)
    parts = [sections.get("summary", ""), sections.get("why", "")]
    return "\n".join(p for p in parts if p)


def _has_unexcused_suppression(text: str) -> bool:
    """True when ``text`` states a suppression intent that isn't reasoned-over.

    Each :data:`_SUPPRESSION_INTENT_RE` match is excused when its lookback
    window trips :data:`_SUPPRESSION_REASONING_RE` (class-of-units or
    detect/flag deliverable), or when the *current sentence* carries an
    explicit deliberate-design statement (:data:`_DELIBERATE_DESIGN_RE`). The
    text trips only if *some* match survives — i.e. an own-deliverable
    suppression that nothing in front of it reframes.
    """
    for m in _SUPPRESSION_INTENT_RE.finditer(text):
        verb_start = m.start(1)
        window = text[max(0, verb_start - _SUPPRESSION_LOOKBACK) : verb_start]
        if _SUPPRESSION_REASONING_RE.search(window):
            continue
        # Sentence-scoped: start after the last terminator/newline in the
        # window, so a deliberate statement about something else can't reach
        # across a sentence boundary to excuse this verb.
        sentence_start = max(
            window.rfind("."), window.rfind("\n"), window.rfind("!"), window.rfind("?")
        )
        if _DELIBERATE_DESIGN_RE.search(window[sentence_start + 1 :]):
            continue
        return True
    return False


def validate_feature_refs(plan: Plan) -> list[Recommendation]:
    """Advisory id-hygiene check over the step-1 ``features`` layer.

    Emits one ``info`` / ``source="feature-ref"`` finding per violation:

      - **duplicate registry id** — the same ``id`` appears twice in
        ``plan.features`` (``step_id=None``).
      - **non-kebab id** — a registry ``id`` fails :data:`_FEATURE_ID_RE`
        (``step_id=None``).
      - **dangling tag** — a ``step.features`` id matches no registry id
        (``step_id=<step>``), the most common authoring mistake (tag a
        step, forget the registry).

    Returns ``[]`` only for a legacy plan that declares *neither* a registry
    *nor* any ``step.features`` tag. A plan that tags steps but declares no
    registry is **not** an early return — every tag dangles, which is exactly
    what the dangling check should flag. Never raises: this is the advisory
    mirror of the parse-time validator the schema deliberately omits.
    """
    tagged = any(step.features for step in plan.steps)
    if not plan.features and not tagged:
        return []

    recs: list[Recommendation] = []

    registry_ids = [f.id for f in plan.features]
    counts = Counter(registry_ids)
    flagged_dups: set[str] = set()
    for feat in plan.features:
        if counts[feat.id] > 1 and feat.id not in flagged_dups:
            flagged_dups.add(feat.id)
            recs.append(
                Recommendation(
                    id=_make_rec_id(None, "feature-ref", f"duplicate:{feat.id}"),
                    source="feature-ref",
                    severity="info",
                    step_id=None,
                    title=f"Duplicate feature id `{feat.id}` in the registry",
                    body=(
                        f"Feature id `{feat.id}` is declared {counts[feat.id]} "
                        "times in `features:`. Registry ids must be unique so a "
                        "`step.features` tag resolves to exactly one feature."
                    ),
                    suggested_action=(
                        f"remove the duplicate `features:` entry for `{feat.id}`"
                    ),
                )
            )

    for feat in plan.features:
        if not _FEATURE_ID_RE.match(feat.id):
            recs.append(
                Recommendation(
                    id=_make_rec_id(None, "feature-ref", f"non-kebab:{feat.id}"),
                    source="feature-ref",
                    severity="info",
                    step_id=None,
                    title=f"Non-kebab feature id `{feat.id}`",
                    body=(
                        f"Feature id `{feat.id}` is not kebab-case "
                        "(`^[a-z0-9]+(-[a-z0-9]+)*$`). Use lowercase "
                        "hyphen-separated tokens so ids stay stable and "
                        "URL/slug-safe."
                    ),
                    suggested_action=(
                        f"rename `{feat.id}` to a kebab-case id"
                    ),
                )
            )

    valid_ids = set(registry_ids)
    for step in plan.steps:
        for tag in step.features:
            if tag not in valid_ids:
                recs.append(
                    Recommendation(
                        id=_make_rec_id(
                            step.id, "feature-ref", f"dangling:{step.id}:{tag}"
                        ),
                        source="feature-ref",
                        severity="info",
                        step_id=step.id,
                        title=(
                            f"Step {step.id} tags unknown feature `{tag}`"
                        ),
                        body=(
                            f"Step {step.id} lists feature `{tag}` in its "
                            "`features:` tag, but no `features:` registry "
                            "entry declares that id."
                        ),
                        suggested_action=(
                            f"add `{tag}` to the plan-level `features:` "
                            f"registry, or fix the tag on step {step.id}"
                        ),
                    )
                )

    return recs


# Single-source the intent-presence source token so the detector below, its
# ``SMELL_DETECTORS`` entry, ``SELF_CONSISTENCY_SOURCES``, and
# ``triage_reason``'s branch key on one symbol.
INTENT_PRESENCE_SOURCE = "intent-presence"


def is_usable_intent(value: Optional[str]) -> bool:
    """True when ``value`` is an intent someone actually wrote.

    Presence is the *entire* contract — absent, empty after whitespace, and a
    bare TODO/TBD marker are the only three non-values. Nothing here judges an
    intent's quality, shape, or length.

    The one predicate ``create``, the intent proposer, and
    ``check_intent_presence`` all share: a change here changes what all three
    accept, so widen or narrow it in one place rather than copying the rule.
    """
    if value is None:
        return False
    # Emptiness first: ``_body_section_is_placeholder`` returns False for an
    # empty string, so asking it first would pass ``""`` off as usable.
    if not value.strip():
        return False
    return not _body_section_is_placeholder(value)


def check_intent_presence(plan: Plan) -> list[Recommendation]:
    """Blocking check on the plan's and its steps' ``intent`` field.

    At most **two** ``medium`` / ``source="intent-presence"`` findings per plan,
    both ``step_id=None``: one for the plan-level field, and one *roll-up*
    naming every step that lacks an intent. A per-step finding would scale
    blocking volume with step count on a corpus where every plan predates the
    field — enough noise to train operators out of the whole channel.
    The two altitudes are independent: report both when both are absent.

    ``medium`` puts the source in :data:`SELF_CONSISTENCY_SOURCES`, so a
    missing intent blocks completeness convergence. The remedy is a one-line
    frontmatter edit, never an ``apply_finding`` pass.

    Never echoes the value it read. A multi-line intent could otherwise open a
    line with ``##`` and forge a heading in the rendered report, and quoting it
    back invites a quality comparison this check must not make.
    """
    recs: list[Recommendation] = []

    if not is_usable_intent(plan.intent):
        recs.append(
            Recommendation(
                id=_make_rec_id(None, INTENT_PRESENCE_SOURCE, "plan-intent"),
                source=INTENT_PRESENCE_SOURCE,
                severity="medium",
                step_id=None,
                title="Plan declares no `intent`",
                body=(
                    "The plan's `intent:` is absent, empty, or a placeholder. "
                    "One line on why this plan exists travels with it into "
                    "every authoring and execution prompt — it is the positive "
                    "half of the plan's scope fence."
                ),
                suggested_action=(
                    "add a one-line `intent:` to the plan frontmatter"
                ),
            )
        )

    missing_ids = sorted(
        step.id for step in plan.steps if not is_usable_intent(step.intent)
    )
    if missing_ids:
        id_list = ", ".join(str(i) for i in missing_ids)
        fingerprint = "step-intent:" + ",".join(str(i) for i in missing_ids)
        recs.append(
            Recommendation(
                id=_make_rec_id(None, INTENT_PRESENCE_SOURCE, fingerprint),
                source=INTENT_PRESENCE_SOURCE,
                severity="medium",
                step_id=None,
                title=f"{len(missing_ids)} step(s) declare no `intent`",
                body=(
                    f"Step(s) {id_list} carry no usable `intent:` (absent, "
                    "empty, or a placeholder). One line on why a step exists "
                    "travels with it into its detail and run prompts — it is "
                    "the positive half of that step's scope fence."
                ),
                suggested_action=(
                    f"add a one-line `intent:` to step(s) {id_list}"
                ),
            )
        )

    return recs


def detect_suppression_shape(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[Recommendation]:
    """Flag a step whose *own deliverable* suppresses an existing audit gate.

    Scans each step's title plus its detail body's ``## Summary`` / ``## Why``
    sections (the motivating ``type_impure`` stated its suppressing purpose in
    its rationale). The body resolves through :func:`_resolve_detail_body` —
    pass ``plan_path`` to also scan a step whose ``detail:`` pointer is unset
    but whose canonical file is on disk. A step with no readable body is
    scanned title-only.

    The trip predicate is a verb→gate-object match
    (:data:`_SUPPRESSION_INTENT_RE`), not a bare keyword. The non-trip guard
    (:data:`_SUPPRESSION_REASONING_RE`) excuses a match that is reasoned over
    rather than performed:

      - **trips**: ``"downgrade the mixed-step finding"`` — own purpose.
      - **does not trip (class-of-units)**: ``"any step that suppresses a
        gate"`` — reasoning over other units.
      - **does not trip (detect/flag deliverable)**: this step's own
        ``## Summary`` ``"detect_suppression_shape (… whose own deliverable
        suppresses an existing audit gate)"`` — the action is to *detect*
        suppression, not perform it.

    Works on a bare step with no ``features:`` block — the one check useful
    before any feature is declared. ``source="suppression-shape"``,
    ``severity="medium"``, ``step_id=<step>``.
    """
    recs: list[Recommendation] = []
    for step in plan.steps:
        scanned = step.title
        body = _read_detail_body(
            step, repo_root, max_bytes, plan=plan, plan_path=plan_path
        )
        if body:
            scanned = step.title + "\n" + _summary_and_why_text(body)
        if not _has_unexcused_suppression(scanned):
            continue
        recs.append(
            Recommendation(
                id=_make_rec_id(
                    step.id, SUPPRESSION_SHAPE_SOURCE, f"suppression:{step.id}"
                ),
                source=SUPPRESSION_SHAPE_SOURCE,
                severity="medium",
                step_id=step.id,
                title=(
                    f"Step {step.id}: deliverable suppresses an existing gate"
                ),
                body=(
                    f"Step {step.id}'s title or detail (`## Summary` / `## "
                    "Why`) states its own deliverable suppresses/downgrades/"
                    "bypasses an existing audit gate, check, finding, or "
                    "severity. Silencing a quality gate is a brittle shape — "
                    "confirm the gate is wrong rather than the step that "
                    "trips it."
                ),
            )
        )
    return recs


# Single-source the orphaned-deliverable source token so the detector here and
# the completeness-side wiring key on one symbol.
ORPHANED_DELIVERABLE_SOURCE = "orphaned-deliverable"

# Single-source the claim-vs-delivery source token (advisory: rides
# ``smell_recs``, never the blocking ``self_consistency_recs`` bucket).
CLAIM_VS_DELIVERY_SOURCE = "claim-vs-delivery"

# Signed-off concept commitments are complete only through exact persisted
# identifiers.  Coverage is blocking; an unsigned parked decision is merely a
# reminder that the proposed deferral still needs review.
CONCEPT_COVERAGE_SOURCE = "concept-coverage"
CONCEPT_UNSIGNED_DEFERRAL_SOURCE = "concept-unsigned-deferral"
# A flat decision record whose coarse bucket no longer resolves to a plan body
# section: surfaced for operator re-review, non-blocking (kept out of
# ``SELF_CONSISTENCY_SOURCES``).
CONCEPT_BUCKET_MISSING_SOURCE = "concept-bucket-missing"
# A legacy full-tree record whose stored fingerprint drifted: its data may carry
# blocking findings, so we surface one non-blocking re-sync advisory rather than
# silently swallowing them to ``[]``. Also kept out of ``SELF_CONSISTENCY_SOURCES``.
CONCEPT_LEGACY_STALE_SOURCE = "concept-legacy-stale"

# The blocking-capable self-consistency battery: plan-internal defects that gate
# at medium+ but are NOT auto-appliable (``apply_finding``, a prose editor, can't
# rewire a plan or write a frontmatter field) — the fix is a manual plan edit.
# Single-sourced so the finalize gate (``_run_deterministic_checks``) and the
# ``--iterate`` loop's blocking signal agree on membership. Deliberately kept out
# of both ``APPLY_ELIGIBLE_SOURCES`` and ``collect_deterministic_findings``.
SELF_CONSISTENCY_SOURCES: "frozenset[str]" = frozenset(
    {
        SUPPRESSION_SHAPE_SOURCE,
        ORPHANED_DELIVERABLE_SOURCE,
        CONCEPT_COVERAGE_SOURCE,
        INTENT_PRESENCE_SOURCE,
    }
)


def _structured_concept_deferral_is_valid(node: object, plan: Plan) -> bool:
    """Return whether step 4's persisted concept-to-step link is valid.

    The detail deferral contract stores a JSON array of positive step ids in
    ``source_metadata``.  A link must still name a step in this plan and, when
    the concept has explicit owners, name one of those owners.  Prose is never
    inspected here.
    """
    metadata = getattr(node, "source_metadata", {})
    raw_step_ids = metadata.get("detail_deferral_step_ids", "")
    if getattr(node, "decision", "") != "defer" or not raw_step_ids:
        return False
    try:
        step_ids = json.loads(raw_step_ids)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(step_ids, list) or not step_ids:
        return False
    if any(
        not isinstance(step_id, int)
        or isinstance(step_id, bool)
        or step_id < 1
        for step_id in step_ids
    ):
        return False

    known_step_ids = {step.id for step in plan.steps}
    concept_id = getattr(node, "id", "")
    owner_step_ids = {
        step.id for step in plan.steps if concept_id in step.concept_ids
    }
    return any(
        step_id in known_step_ids
        and (not owner_step_ids or step_id in owner_step_ids)
        for step_id in step_ids
    )


def _check_decision_record_coverage(
    concept_tree: "ConceptTree",
    plan_path: Path,
    unsigned_deferral_rec: "Callable[[ConceptNode], Recommendation]",
) -> list[Recommendation]:
    """Audit a flat decision record by coarse-bucket existence.

    A confirmed (``approved``) decision is its own accounting, so it never
    emits a blocking coverage finding. An unreviewed decision whose ``bucket``
    no longer names a current body section surfaces one non-blocking
    ``concept-bucket-missing`` re-review finding; one whose bucket still exists
    keeps the existing unsigned-deferral reminder.  Never raises.
    """
    # "Bucket exists" is the identical normalized section-name lookup step 4's
    # scope-review confirm gate uses, so the two sites agree on what exists. If
    # the body can't be read we can't determine bucket existence, so skip the
    # check rather than emit false findings for every node.
    # "Never raises" is load-bearing (step 3 totality), so guard every way the
    # read can fail: OSError (file gone/unreadable), ParseError (malformed
    # frontmatter fence), and ValueError (e.g. UnicodeDecodeError on non-utf-8).
    # Any of them means bucket existence is undeterminable → skip the check.
    try:
        sections: Optional[dict[str, str]] = split_body_sections(
            _split_frontmatter(plan_path.read_text(encoding="utf-8")).body,
            ignore_fenced_code=True,
        )
    except (OSError, ParseError, ValueError):
        sections = None

    recommendations: list[Recommendation] = []
    for node in sorted(
        concept_tree.concepts,
        key=lambda item: (item.order, item.parent_path, item.id),
    ):
        # An approved decision is the operator's resolution — a gone bucket on
        # it must not re-surface (that is how a `wont_do` clears a
        # missing-bucket record). Skip approved nodes entirely.
        if node.review_state == "approved":
            continue
        if sections is not None and node.bucket not in sections:
            recommendations.append(
                Recommendation(
                    id=_make_rec_id(
                        None, CONCEPT_BUCKET_MISSING_SOURCE, node.id
                    ),
                    source=CONCEPT_BUCKET_MISSING_SOURCE,
                    severity="info",
                    step_id=None,
                    title=f"Concept `{node.id}` bucket no longer exists",
                    body=(
                        f"Concept `{node.id}` ({node.title}) is parked under "
                        f"bucket `{node.bucket}`, which no longer names a plan "
                        "body section. Re-review this decision so it points at "
                        "a current section."
                    ),
                    suggested_action=(
                        "re-review this decision with `plan-tool scope-review`"
                    ),
                    anchor=f"concept-{node.id}",
                )
            )
            continue
        if node.decision in {"defer", "wont_do"}:
            recommendations.append(unsigned_deferral_rec(node))
    return recommendations


def check_concept_coverage(
    plan: Plan,
    plan_path: Optional[Path],
    *,
    plan_name: str,
) -> list[Recommendation]:
    """Audit signed-off concepts using explicit ownership/deferral links.

    A missing record is intentionally inert.  Approved concepts are covered
    by an exact id on any committed step, an approved ``wont_do`` decision,
    or a valid structured detail deferral.  Unreviewed parked decisions emit
    a separate info reminder and never become blocking commitments.
    """
    if plan_path is None:
        return []

    from plan_tool.concept_tree import (
        InvalidConceptTreeError,
        RECORD_KIND_DECISION,
        StaleConceptTreeError,
        concepts_path,
        load_concepts,
    )
    from plan_tool.review_persistence import compute_plan_fingerprint

    # Preserve the absent-record contract without even deriving a plan
    # fingerprint. Besides avoiding needless work, this keeps completeness
    # inert when no concept workflow has been started.
    if not concepts_path(plan_path).is_file():
        return []
    # Make the load total: a malformed record is truly unreadable (inert []),
    # while a stale legacy full-tree record still carries (possibly blocking)
    # data, so surface one non-blocking re-sync advisory instead of swallowing
    # it. Only the legacy kind raises StaleConceptTreeError (step 1 skips the
    # fingerprint guard for flat records).
    try:
        concept_tree = load_concepts(
            plan_path, compute_plan_fingerprint(plan_path)
        )
    except InvalidConceptTreeError:
        return []
    except StaleConceptTreeError:
        return [
            Recommendation(
                id=_make_rec_id(None, CONCEPT_LEGACY_STALE_SOURCE, plan_name),
                source=CONCEPT_LEGACY_STALE_SOURCE,
                severity="info",
                step_id=None,
                title="Concept record is fingerprint-drifted",
                body=(
                    "The legacy concept record has drifted from the current "
                    "plan, so its concept coverage cannot be re-checked. "
                    "Re-sync it with `plan-tool scope-review` to restore "
                    "coverage checking."
                ),
                suggested_action=(
                    "re-sync the concept record with `plan-tool scope-review`"
                ),
                anchor="concept-legacy-stale",
            )
        ]
    if concept_tree is None:
        return []

    def _unsigned_deferral_rec(node: ConceptNode) -> Recommendation:
        return Recommendation(
            id=_make_rec_id(None, CONCEPT_UNSIGNED_DEFERRAL_SOURCE, node.id),
            source=CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
            severity="info",
            step_id=None,
            title=f"Concept `{node.id}` deferral is not signed off",
            body=(
                f"Concept `{node.id}` ({node.title}) has a proposed "
                f"`{node.decision}` decision that is not reviewed; "
                "review the concept decision before relying on it."
            ),
            suggested_action=(
                "review and approve or reject the concept decision"
            ),
            anchor=f"concept-{node.id}",
        )

    # Flat decision records are validated only by bucket existence (a coarse
    # section-name lookup against the current body); a confirmed decision is
    # itself the accounting, so it never emits the blocking coverage finding.
    # Use the identical parse recipe scope-review's confirm gate uses so the two
    # sites can never disagree on what "exists" means.
    if concept_tree.record_kind == RECORD_KIND_DECISION:
        return _check_decision_record_coverage(
            concept_tree, plan_path, _unsigned_deferral_rec
        )

    committed_concept_ids = {
        concept_id
        for step in plan.steps
        if step.scope is StepScope.COMMITTED
        for concept_id in step.concept_ids
    }
    recommendations: list[Recommendation] = []
    for node in sorted(
        concept_tree.concepts,
        key=lambda item: (item.order, item.parent_path, item.id),
    ):
        if node.review_state != "approved":
            if node.decision in {"defer", "wont_do"}:
                recommendations.append(_unsigned_deferral_rec(node))
            continue
        if (
            node.id in committed_concept_ids
            or node.decision == "wont_do"
            or _structured_concept_deferral_is_valid(node, plan)
        ):
            continue
        recommendations.append(
            Recommendation(
                id=_make_rec_id(None, CONCEPT_COVERAGE_SOURCE, node.id),
                source=CONCEPT_COVERAGE_SOURCE,
                severity="medium",
                step_id=None,
                title=f"Concept `{node.id}` has no explicit accounting link",
                body=(
                    f"Signed-off concept `{node.id}` ({node.title}) has neither "
                    "an exact owner on a committed step nor a valid structured "
                    "deferral. Assign this concept ID to a committed step or "
                    "record a reviewed structured deferral."
                ),
                suggested_action=(
                    "assign the concept ID to a committed step or record a "
                    "reviewed structured deferral"
                ),
                anchor=f"concept-{node.id}",
            )
        )
    return recommendations


def _deliverable_deferred(
    step: Step,
    repo_root: Path,
    plan_deferred_paths: set[str],
    identity_paths: set[str],
    identity_symbols: set[str],
    max_bytes: int,
    *,
    plan: Optional[Plan] = None,
    plan_path: Optional[Path] = None,
) -> bool:
    """True when the step defers *this deliverable's* wiring (condition 4).

    Plan-level deferral is matched on explicit **path only** (``plan_deferred_paths``
    is shared across steps, so a coincidental symbol match would over-fire); the
    step's *own* deferred sections match path or path-derived symbol.
    """
    from plan_tool.detail import extract_path_mentions, parse_detail_file_sections

    if identity_paths & plan_deferred_paths:
        return True

    body = _read_detail_body(
        step, repo_root, max_bytes,
        plan=plan, plan_path=plan_path,
    )
    if not body:
        return False
    sections = parse_detail_file_sections(body)
    # ``## Deferred`` -> ``deferred``; ``## Out of scope`` -> ``out``.
    step_deferred = "\n".join(
        t for t in (sections.get("deferred", ""), sections.get("out", "")) if t
    )
    if not step_deferred:
        return False
    deferred_paths = _normalize_paths(extract_path_mentions(step_deferred))
    deferred_symbols = _prose_symbols(step_deferred)
    return bool(
        (identity_paths & deferred_paths) or (identity_symbols & deferred_symbols)
    )


def detect_orphaned_deliverable(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[Recommendation]:
    """Flag a step that ships a deliverable nothing consumes and defers its wiring.

    The dead-on-arrival shape: a non-``done`` step introduces a ``creates:``/
    ``files:`` path (or a path-derived symbol) that no *other* in-scope step or
    plan claim consumes, and the step itself defers the wiring. Generalizes
    :func:`check_files_coherence` (a step vs its own footprint) to the plan-wide
    question "does anything else consume what this step delivers?".

    Trip is a four-part conjunction, so the check stays crisp:

      1. a non-done step declares a deliverable (path or path-derived symbol);
      2. no *other* in-scope step references it (a co-declaration or a
         detail-body path/symbol mention — the footprint's referenced side);
      3. no plan claim (``## Acceptance criteria`` / ``## Overview``) names it;
      4. the step defers its own wiring (its detail ``## Deferred`` / ``## Out of
         scope``, or the plan's, names the deliverable).

    Conservative by construction: it keys only on declared paths, path-derived
    symbols, and step-ids (exact-string after normalization) — never a bare
    English noun (the free-text-similarity alternative is rejected; fuzzy
    near-matching is the later ``claim-vs-delivery`` detector's concern). A
    later step that consumes the deliverable satisfies condition 2 and the
    finding never fires — a false negative is preferred over nagging. (The
    per-condition identity breadth is an accepted precision tradeoff — see
    BACKLOG #111.)

    Skips ``done`` steps (a delivered step's wiring is the semantic review's
    job, matching :func:`check_files_coherence` / :func:`heuristic_already_done`)
    and reads only plan/detail markdown, never a source file.

    ``source="orphaned-deliverable"``, ``severity="medium"``, ``step_id=<step>``.
    """
    from plan_tool.detail import extract_path_mentions

    # Parse the plan body once and thread it into the footprint build (which
    # would otherwise re-read/parse the plan file for its claim prose).
    plan_sections = _plan_body_sections(plan_path)
    footprint = build_plan_footprint(
        plan, repo_root, plan_path=plan_path,
        plan_sections=plan_sections, max_bytes=max_bytes,
    )
    plan_deferred_text = "\n".join(
        text
        for key in ("deferred", "out of scope")
        if (text := plan_sections.get(key, ""))
    )
    # Plan-level deferred paths are constant across the whole detect run —
    # extract once, not per (step, deliverable).
    plan_deferred_paths = _normalize_paths(extract_path_mentions(plan_deferred_text))

    recs: list[Recommendation] = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        declared_paths = footprint.declared_paths_by_step.get(
            step.id, frozenset()
        )
        for path in sorted(declared_paths):
            identity_paths = {path}
            identity_symbols = {
                s.lower() for s in _derive_file_path_symbols(path)
            }
            # Condition 2 matches across *other* steps, where a shared directory
            # token would collide broadly — key it on filename-only symbols. The
            # full path-derived identity (incl. the directory token) is kept for
            # conditions 3/4, which match the deliverable against its *own*
            # claim / deferred prose where that token is a legitimate reference.
            consumer_symbols = {
                s.lower()
                for s in _derive_file_path_symbols(PurePosixPath(path).name)
            }
            # Condition 2: consumed by another in-scope step?
            if _referenced_outside_step(
                step.id, identity_paths, consumer_symbols, footprint
            ):
                continue
            # Condition 3: named by a plan/detail claim?
            if (identity_paths & footprint.claim_paths) or (
                identity_symbols & footprint.claim_symbols
            ):
                continue
            # Condition 4: the step defers this deliverable's wiring?
            if not _deliverable_deferred(
                step,
                repo_root,
                plan_deferred_paths,
                identity_paths,
                identity_symbols,
                max_bytes,
                plan=plan,
                plan_path=plan_path,
            ):
                continue
            recs.append(
                Recommendation(
                    id=_make_rec_id(
                        step.id, ORPHANED_DELIVERABLE_SOURCE, f"orphan:{path}"
                    ),
                    source=ORPHANED_DELIVERABLE_SOURCE,
                    severity="medium",
                    step_id=step.id,
                    title=(
                        f"Step {step.id}: deliverable `{path}` has no in-scope "
                        "consumer"
                    ),
                    body=(
                        f"Step {step.id} declares `{path}`, but no other "
                        "in-scope step or plan claim (`## Acceptance criteria` "
                        "/ `## Overview`) consumes it, and the step defers its "
                        "own wiring (`## Deferred` / `## Out of scope`). A "
                        "deliverable nothing consumes lands dead on arrival. "
                        "Confirm it is needed now, or move it to the step that "
                        "wires it in."
                    ),
                )
            )
    return recs


def _referenced_outside_step(
    step_id: int,
    paths: set[str],
    symbols: set[str],
    footprint: PlanFootprint,
) -> bool:
    """True when an in-scope step other than ``step_id`` references the tokens.

    A reference is a co-declaration (another step declares the exact path) or a
    detail-body path/symbol mention. ``symbols`` are the deliverable's
    filename-derived identity symbols (no directory tokens — see the caller), so
    a sibling merely sharing a package directory does not cross-suppress. Reads
    the footprint's per-step maps only — no file access.
    """
    for other_id in footprint.declared_paths_by_step:
        if other_id == step_id:
            continue
        if paths & footprint.declared_paths_by_step.get(other_id, frozenset()):
            return True
        if paths & footprint.referenced_paths_by_step.get(other_id, frozenset()):
            return True
        if symbols & footprint.referenced_symbols_by_step.get(
            other_id, frozenset()
        ):
            return True
    return False


def _claim_prose_symbols(text: str) -> set[str]:
    """Backtick-quoted, code-shaped identifier tokens from claim prose.

    Pulls each backtick span and keeps only single-token, non-path mentions
    that look like code (:func:`plan_tool.create._looks_like_code` — snake_case,
    CamelCase, dotted, digit-bearing, or ``@$``-punctuated). A phrase in
    backticks, a path (handled by :func:`plan_tool.detail.extract_path_mentions`),
    and a plain English word are all dropped: prose must be code-shaped to count
    as a deliverable claim, which is the whole false-positive guard.
    """
    from plan_tool.create import _looks_like_code

    out: set[str] = set()
    for m in re.finditer(r"`([^`]+)`", text):
        raw = m.group(1).strip()
        if not raw or any(ch.isspace() for ch in raw) or "/" in raw:
            continue
        if _looks_like_code(raw):
            out.add(raw.lower())
    return out


def _claim_delivered(token: str, declared: Iterable[str]) -> bool:
    """True when ``token`` matches a declared path/symbol — exact or near-miss.

    Exact after lowercase, else a :class:`difflib.SequenceMatcher` ratio at or
    above :data:`_NEAR_MISS_RATIO` (the fuzzy convention
    :func:`check_files_coherence` uses). The fuzzy step tolerates minor naming
    variance (``foo_widgets`` vs a declared ``foo_widget``).
    """
    for d in declared:
        if token == d:
            return True
        if SequenceMatcher(None, token, d).ratio() >= _NEAR_MISS_RATIO:
            return True
    return False


def detect_claim_vs_delivery(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
    max_bytes: int = _MAX_DETAIL_PARSE_BYTES,
) -> list[Recommendation]:
    """Flag a deliverable the plan's ``## Acceptance criteria`` prose claims that
    no step's declared footprint delivers.

    The inverse of :func:`detect_orphaned_deliverable` ("does anything consume
    this deliverable?"): this asks "does any step *deliver* this claim?".
    ``## Acceptance criteria`` is the sole deliverable-pinning section —
    ``## Overview`` routinely names pre-existing/context symbols the plan builds
    on, so a token appearing only there is never flagged. Reuses step 3's
    :func:`build_plan_footprint` declared side as the delivered set and matches
    each artifact-shaped claim token against it (exact or fuzzy).
    """
    from plan_tool.detail import extract_path_mentions

    acceptance = _excise_fenced_code(
        _plan_body_sections(plan_path).get("acceptance criteria", "")
    )
    if not acceptance:
        return []
    claim_paths = sorted(_normalize_paths(extract_path_mentions(acceptance)))
    claim_symbols = sorted(_claim_prose_symbols(acceptance))
    if not claim_paths and not claim_symbols:
        return []

    # Only the *declared* side is consumed here, and it derives from
    # ``step.all_files`` with zero file I/O — so use the declared-only helper
    # rather than the full footprint (whose detail-body reads would be discarded).
    declared_paths_by_step, declared_symbols_by_step = _declared_footprint(plan)
    declared_paths = {
        p.lower() for s in declared_paths_by_step.values() for p in s
    }
    declared_symbols = {
        s for step in declared_symbols_by_step.values() for s in step
    }  # already lowercased

    recs: list[Recommendation] = []
    for token, declared in (
        *((p, declared_paths) for p in claim_paths),
        *((s, declared_symbols) for s in claim_symbols),
    ):
        if _claim_delivered(token.lower(), declared):
            continue
        recs.append(
            Recommendation(
                id=_make_rec_id(
                    None, CLAIM_VS_DELIVERY_SOURCE, f"claim:{token}"
                ),
                source=CLAIM_VS_DELIVERY_SOURCE,
                severity="info",
                step_id=None,
                title=(
                    f"Plan claims `{token}` but no step delivers it"
                ),
                body=(
                    f"The plan's `## Acceptance criteria` names `{token}`, but "
                    "no step's declared footprint (`creates:` / `files:`, or a "
                    "path-derived symbol) delivers it — even by fuzzy match. "
                    "Confirm a step delivers it, or drop the claim. Advisory: "
                    "fuzzy prose matching can false-positive, so this never "
                    "blocks."
                ),
            )
        )
    return recs


def detect_self_referential_features(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
) -> list[Recommendation]:
    """Flag a feature whose file set overlaps the tool's own audit machinery.

    The comparison set is read from
    ``project_config.validation_machinery_paths(repo_root)`` and the detector
    is **inert when unconfigured** — returns ``[]`` immediately on an empty
    set, so a general-purpose tool never couples to its own source tree.
    Returns ``[]`` when ``plan.features`` is empty (requires the feature
    layer).

    A feature's file set is the union of ``step.all_files`` over the steps
    whose ``step.features`` tag includes that feature id (ownership runs
    step → feature). Emits one ``info`` / ``source="self-referential"``
    finding per feature whose set overlaps the machinery set (compared as
    normalized POSIX strings). ``step_id=None`` (feature-level).
    """
    if not plan.features:
        return []
    from plan_tool import project_config

    machinery = project_config.validation_machinery_paths(repo_root)
    if not machinery:
        return []
    machinery_set = {str(PurePosixPath(p)) for p in machinery}

    recs: list[Recommendation] = []
    for feat in plan.features:
        file_set: set[str] = set()
        for step in plan.steps:
            if feat.id in step.features:
                file_set.update(step.all_files)
        overlap = sorted(
            p for p in file_set if str(PurePosixPath(p)) in machinery_set
        )
        if not overlap:
            continue
        paths_str = ", ".join(f"`{p}`" for p in overlap)
        recs.append(
            Recommendation(
                id=_make_rec_id(
                    None,
                    "self-referential",
                    f"{feat.id}:" + ",".join(overlap),
                ),
                source="self-referential",
                severity="info",
                step_id=None,
                title=(
                    f"Feature `{feat.id}` modifies the audit machinery"
                ),
                body=(
                    f"Feature `{feat.id}` ({feat.title}) has a file set that "
                    f"overlaps the configured validation machinery: "
                    f"{paths_str}. A feature that changes the very machinery "
                    "the audit runs through can mask its own regressions — "
                    "review it with extra care."
                ),
            )
        )
    return recs


@dataclass(frozen=True)
class DetectorContext:
    """Inputs shared by deterministic completeness detectors."""

    plan: Plan
    repo_root: Path
    plan_name: str
    plan_path: Optional[Path] = None


@dataclass(frozen=True)
class DetectorEntry:
    """One deterministic detector with explicit producer dependencies and finding sources."""

    key: str
    call: Callable[[DetectorContext, Mapping[str, object]], object]
    consumes: tuple[str, ...] = ()
    finding_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class DetectorRegistry:
    """An ordered table of :class:`DetectorEntry` — the only path to a
    deterministic completeness detector.

    One policy: run every entry, in declaration order, so findings land in the
    order the battery has always rendered them.
    """

    entries: tuple[DetectorEntry, ...]

    def __post_init__(self) -> None:
        # Coerced so a table built from a comprehension still chains.
        object.__setattr__(self, "entries", tuple(self.entries))
        produced: set[str] = set()
        for entry in self.entries:
            if entry.key in produced:
                raise ValueError(f"duplicate detector key {entry.key!r}")
            for producer in entry.consumes:
                if producer not in produced:
                    raise ValueError(
                        f"detector {entry.key!r} consumes {producer!r}, which "
                        "no earlier entry in this registry produces"
                    )
            produced.add(entry.key)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(entry.key for entry in self.entries)

    def chain(self, *others: DetectorRegistry) -> DetectorRegistry:
        """One registry spanning this table and ``others``, order preserved."""
        entries = self.entries
        for other in others:
            entries = entries + other.entries
        return DetectorRegistry(entries)


    def run_all(self, ctx: DetectorContext) -> dict[str, object]:
        """Run every entry once, in order, keyed by entry key."""
        results: dict[str, object] = {}
        for entry in self.entries:
            results[entry.key] = entry.call(ctx, results)
        return results


# The plan-level well-formedness detectors, in battery order: correctness
# primitives (file existence, path style, deps) ahead of completeness ones
# (body sections, detail coverage, detail bodies, files coherence, lessons).
PLAN_WELL_FORMEDNESS_DETECTORS = DetectorRegistry(
    (
        DetectorEntry(
            "file-existence",
            lambda ctx, results: check_file_existence(ctx.plan, ctx.repo_root),
        ),
        DetectorEntry(
            "path-style-mismatch",
            lambda ctx, results: detect_path_style_mismatch(
                results["file-existence"], ctx.repo_root
            ),
            consumes=("file-existence",),
        ),
        DetectorEntry(
            "deps",
            lambda ctx, results: validate_deps(ctx.plan),
        ),
        DetectorEntry(
            "body-completeness",
            lambda ctx, results: check_body_completeness(ctx.plan_path),
        ),
        DetectorEntry(
            "detail-coverage",
            lambda ctx, results: check_detail_coverage(
                ctx.plan, ctx.plan_path, ctx.repo_root
            ),
        ),
        DetectorEntry(
            "detail-body-completeness",
            lambda ctx, results: check_detail_body_completeness(
                ctx.plan, ctx.repo_root, plan_path=ctx.plan_path
            ),
        ),
        DetectorEntry(
            "files-coherence",
            lambda ctx, results: check_files_coherence(
                ctx.plan, ctx.repo_root, plan_path=ctx.plan_path
            ),
        ),
        DetectorEntry(
            "lessons-coverage",
            lambda ctx, results: check_lessons_coverage(
                ctx.plan, ctx.repo_root
            ),
        ),
    )
)

INPUT_CONTRACT_DETECTORS = DetectorRegistry(
    (
        DetectorEntry(
            "input-contract-references-plan",
            lambda ctx, results: check_plan_input_contract_references(
                ctx.plan, ctx.plan_path, ctx.repo_root
            ),
        ),
        DetectorEntry(
            "input-contract-references-steps",
            lambda ctx, results: check_step_input_contract_references(
                ctx.plan, ctx.plan_path, ctx.repo_root
            ),
        ),
    )
)

# The advisory smell fan-out, in the order ``collect_smell_findings``
# concatenates them.
SMELL_DETECTORS = DetectorRegistry(
    (
        DetectorEntry(
            "feature-refs",
            lambda ctx, results: validate_feature_refs(ctx.plan),
            finding_sources=("feature-ref",),
        ),
        DetectorEntry(
            "suppression-shape",
            lambda ctx, results: detect_suppression_shape(
                ctx.plan,
                ctx.repo_root,
                plan_name=ctx.plan_name,
                plan_path=ctx.plan_path,
            ),
            finding_sources=(SUPPRESSION_SHAPE_SOURCE,),
        ),
        DetectorEntry(
            "self-referential-features",
            lambda ctx, results: detect_self_referential_features(
                ctx.plan, ctx.repo_root, plan_name=ctx.plan_name
            ),
            finding_sources=("self-referential",),
        ),
        DetectorEntry(
            "claim-vs-delivery",
            lambda ctx, results: detect_claim_vs_delivery(
                ctx.plan,
                ctx.repo_root,
                plan_name=ctx.plan_name,
                plan_path=ctx.plan_path,
            ),
            finding_sources=(CLAIM_VS_DELIVERY_SOURCE,),
        ),
        DetectorEntry(
            "concept-coverage",
            lambda ctx, results: check_concept_coverage(
                ctx.plan, ctx.plan_path, plan_name=ctx.plan_name
            ),
            finding_sources=(
                CONCEPT_COVERAGE_SOURCE,
                CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
                CONCEPT_LEGACY_STALE_SOURCE,
                CONCEPT_BUCKET_MISSING_SOURCE,
            ),
        ),
        DetectorEntry(
            "intent-presence",
            lambda ctx, results: check_intent_presence(ctx.plan),
            finding_sources=(INTENT_PRESENCE_SOURCE,),
        ),
    )
)

# The one self-consistency detector that is never a smell, so it is always
# computed fresh rather than partitioned off the smell fan-out.
SELF_CONSISTENCY_DETECTORS = DetectorRegistry(
    (
        DetectorEntry(
            "orphaned-deliverable",
            lambda ctx, results: detect_orphaned_deliverable(
                ctx.plan,
                ctx.repo_root,
                plan_name=ctx.plan_name,
                plan_path=ctx.plan_path,
            ),
            finding_sources=(ORPHANED_DELIVERABLE_SOURCE,),
        ),
    )
)

# The smell entries that can mint a blocking self-consistency source — derived,
# not hand-listed, so :func:`collect_self_consistency_findings` cannot drift
# from the gate's partition over :data:`SELF_CONSISTENCY_SOURCES`.
SELF_CONSISTENCY_SMELL_DETECTORS = DetectorRegistry(
    tuple(
        entry
        for entry in SMELL_DETECTORS
        if not SELF_CONSISTENCY_SOURCES.isdisjoint(entry.finding_sources)
    )
)


def collect_smell_findings(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
) -> list[Recommendation]:
    """Dispatch :data:`SMELL_DETECTORS` into one flat list.

    Feature-ref validation, suppression shape, self-referential features, the
    advisory ``claim-vs-delivery`` check (a deliverable the plan's ``##
    Acceptance criteria`` claims that no step delivers), concept coverage, and
    ``intent`` presence. Not all of them are advisory: the entries minting a
    :data:`SELF_CONSISTENCY_SOURCES` finding (suppression shape, concept
    coverage, ``intent`` presence) are partitioned onto the blocking bucket by
    the completeness battery — this fan-out is *where they are computed*, not a
    claim about severity.
    Deliberately **not** wired into :func:`collect_deterministic_findings` (the
    broadcast fan-out feeding the ``--iterate`` apply loop) — appending there
    would route advisory smells into ``apply_finding``, a prose editor that
    cannot fix a brittle structural shape.

    ``plan_path`` is optional so a caller holding only a parsed :class:`Plan`
    still works: without it the claim-vs-delivery check has no plan body to
    read and yields nothing, but the other detectors run unchanged.
    """
    ctx = DetectorContext(
        plan=plan,
        repo_root=repo_root,
        plan_name=plan_name,
        plan_path=plan_path,
    )
    recs: list[Recommendation] = []
    for found in SMELL_DETECTORS.run_all(ctx).values():
        recs.extend(found)
    return recs


def _self_consistency_from_smells(
    smell_recs: list[Recommendation],
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
) -> list[Recommendation]:
    """The self-consistency battery given already-computed ``smell_recs``.

    Assembly, not a detector: every :data:`SELF_CONSISTENCY_SOURCES` rec
    partitioned off the already-computed smell fan-out (so those detectors run
    once per audit, not once per consumer), plus
    :data:`SELF_CONSISTENCY_DETECTORS`' ``orphaned-deliverable`` recs.
    Single source for the membership shared by
    :func:`collect_self_consistency_findings` and ``_run_deterministic_checks``.
    """
    ctx = DetectorContext(
        plan=plan,
        repo_root=repo_root,
        plan_name=plan_name,
        plan_path=plan_path,
    )
    recs = [
        rec for rec in smell_recs if rec.source in SELF_CONSISTENCY_SOURCES
    ]
    for found in (
        SELF_CONSISTENCY_DETECTORS.run_all(ctx).values()
    ):
        recs.extend(found)
    return recs


def collect_self_consistency_findings(
    plan: Plan,
    repo_root: Path,
    *,
    plan_name: str,
    plan_path: Optional[Path] = None,
) -> list[Recommendation]:
    """The blocking-capable self-consistency battery, computed independently."""
    ctx = DetectorContext(
        plan=plan,
        repo_root=repo_root,
        plan_name=plan_name,
        plan_path=plan_path,
    )
    recs: list[Recommendation] = []
    for found in (
        SELF_CONSISTENCY_SMELL_DETECTORS
        .run_all(ctx)
        .values()
    ):
        recs.extend(
            rec for rec in found if rec.source in SELF_CONSISTENCY_SOURCES
        )
    for found in (
        SELF_CONSISTENCY_DETECTORS.run_all(ctx).values()
    ):
        recs.extend(found)
    return recs


def render_review_prompt(
    plan: Plan,
    repo_root: Path,
    *,
    step_filter: Optional[int] = None,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
    plan_path: Optional[Path] = None,
) -> str:
    """Render ``prompts/review.md`` with the plan's steps, per-step detail
    bodies, and current file contents.

    ``plan_path`` enables canonical resolution: a step whose ``detail:``
    pointer is unset but whose canonical file is on disk gets its body
    rendered too, so the reviewer judges the same bundle the deterministic
    battery emits findings against. Omit it and only pointer-set steps
    render, which is this function's original behavior.
    """
    template_path = prompts_dir() / "review.md"
    template = Template(template_path.read_text(encoding="utf-8"))

    steps_lines: list[str] = []
    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        deps = f" (depends_on={step.depends_on})" if step.depends_on else ""
        # Declared files = ``files:`` (edited) ∪ ``creates:`` (new). Rendering
        # only ``files:`` made a creates-only step read as "declares no files"
        # and its modules as "omitted" — false reconcile findings. Mark the
        # new ones so a pending step's not-yet-created file isn't itself flagged.
        declared = [f"`{f}`" for f in step.files]
        declared += [f"`{f}` (new)" for f in step.creates]
        files_suffix = (
            "\n    files: " + ", ".join(declared) if declared else ""
        )
        # Surface the commitment axis only when the step is parked; a
        # committed step shows status alone (the common case).
        tag = (
            f"{step.status.value}, {step.scope.value}"
            if step.scope is not StepScope.COMMITTED
            else step.status.value
        )
        steps_lines.append(
            f"- {step.id}. [{tag}] {step.title}{deps}{files_suffix}"
        )
    all_steps_block = "\n".join(steps_lines) if steps_lines else "_no steps to review_"

    details_blocks: list[str] = []
    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        # Pointer first, canonical second — the same rule step 2 gave the
        # deterministic checks, so findings describe the bundle this prompt
        # renders. ``plan_path=None`` means no canonical fallback is possible,
        # which keeps pointer-only callers on their previous behavior.
        # ``not step.detail``, not ``is None``: ``resolve_detail_artifact``
        # classifies the pointer with ``bool(step.detail)``, and ``Step.detail``
        # has no non-empty validator, so a plan carrying ``detail: ''`` must
        # take the same branch here as it does in the resolver.
        if not step.detail and plan_path is None:
            continue
        resolution = (
            resolve_detail_artifact(plan_path, plan, step, repo_root)
            if plan_path is not None
            else None
        )
        if (
            resolution is not None
            and not resolution.pointer_set
            and not resolution.on_disk
        ):
            continue
        details_blocks.append(
            _render_step_detail_block(
                step,
                repo_root,
                max_file_bytes=max_file_bytes,
                resolution=resolution,
            )
        )
    step_details_block = (
        "\n".join(details_blocks)
        if details_blocks
        else "_no step detail files declared_"
    )

    path_order: list[str] = []
    path_candidates: dict[str, list[str]] = {}
    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        step_candidates = _derive_symbols(step.title)
        # Both axes: ``creates:`` paths that already exist surface the
        # "already implemented" signal reconcile exists to catch; ones that
        # don't render "(not on disk)" — expected for an unbuilt step.
        for f in (*step.files, *step.creates):
            if f not in path_candidates:
                path_candidates[f] = []
                path_order.append(f)
            _merge_candidate_symbols(path_candidates[f], step_candidates)
            _merge_candidate_symbols(
                path_candidates[f], _derive_file_path_symbols(f)
            )

    contents_blocks: list[str] = []
    for f in path_order:
        path = repo_root / f
        if not path.is_file():
            contents_blocks.append(f"### `{f}` _(not on disk)_\n")
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            contents_blocks.append(f"### `{f}` _(unreadable: {exc})_\n")
            continue
        excerpt = build_prompt_excerpt(
            f,
            body,
            path_candidates[f],
            max_bytes=max_file_bytes,
        )
        contents_blocks.append(
            f"### `{f}`\n\n```\n{excerpt.text}\n```\n"
        )
    files_contents_block = (
        "\n".join(contents_blocks) if contents_blocks else "_no files declared_"
    )

    lessons_block = render_lessons_block(load_lessons(repo_root))

    return template.safe_substitute(
        plan_title=plan.title,
        all_steps_block=all_steps_block,
        step_details_block=step_details_block,
        files_contents_block=files_contents_block,
        lessons_block=lessons_block,
        findings_response_format_block=FINDINGS_RESPONSE_CONTRACT.render_prompt_block(),
    )


def _render_step_detail_block(
    step: Step,
    repo_root: Path,
    *,
    max_file_bytes: int,
    resolution: Optional[DetailArtifactResolution] = None,
) -> str:
    """Render one step's detail file as a markdown section.

    Three branches: missing / unreadable / present. Truncation reuses the
    same ``_MAX_PROMPT_FILE_BYTES`` ceiling as file contents so a long
    detail file can't crowd out source bodies.

    ``resolution`` (from :func:`detail_artifacts.resolve_detail_artifact`)
    supplies the canonical path for a step whose pointer is unset. Without
    it the caller must filter out ``step.detail is None`` steps — the
    pointer-only path this function has always had.
    """
    if resolution is not None and not resolution.pointer_set:
        # Read the path the resolver already verified; the repo-relative form
        # is only a label. Round-tripping the resolved path through a label
        # and back re-derives it against ``repo_root`` while ``on_disk`` was
        # computed against the resolver's own path, so the two can disagree.
        path = resolution.path
        detail_rel = _repo_relative_posix(path, repo_root)
    else:
        assert step.detail, "caller must skip steps with no detail pointer"
        detail_rel = step.detail
        path = repo_root / detail_rel
    header = f"### Step {step.id}: {step.title}"
    if not path.is_file():
        return (
            f"{header}\n\n_detail file `{detail_rel}` declared but not on disk_\n"
        )
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"{header}\n\n_detail file `{detail_rel}` unreadable: {exc}_\n"
    require_supported_detail_format_version(body, path=path)
    snippet = body[:max_file_bytes]
    truncated = "\n… _(truncated)_" if len(body) > max_file_bytes else ""
    return (
        f"{header}\n\n_from `{detail_rel}`:_\n\n{snippet}{truncated}\n"
    )


def _describe_file_check(
    fc: FileCheck,
    *,
    step_status: StepStatus,
) -> tuple[str, Optional[str]]:
    """Format a single ``FileCheck`` into ``(issue_text, suggestion_body)``.

    Returns ``("", None)`` when the check produces no warning — OK files,
    and NEW files on steps that aren't DONE (those are expected creators).

    All paths in the returned text are repo-relative (the same string the
    user wrote in the plan). The absolute repo root is printed once in the
    report header by :func:`assemble_report`, so repeating it on every
    finding line only adds noise.

    For NEW-on-DONE, the suggestion is ``None`` because the actionable
    advice ("run reconcile on step N") needs plan_name and step.id, which
    the caller still has and emits inline.

    ``step_status`` is required because the spec distinguishes NEW-on-DONE
    (an issue) from NEW-on-pending (the expected case for creators).

    Files from the step's ``creates:`` list (``fc.created``) are expected
    to be absent until the step runs, so neither MISSING_PARENT nor NEW
    warns for them — the sole failure mode is a DONE step that never
    produced the file.
    """
    parent_rel = Path(fc.path).parent
    if fc.created:
        if fc.status != FileExistence.OK and step_status == StepStatus.DONE:
            issue = (
                f"`{fc.path}` declared under `creates:` but missing on "
                "disk (step marked done)"
            )
            return (issue, None)
        return ("", None)
    if fc.status == FileExistence.MISSING_PARENT:
        issue = f"`{fc.path}` — parent dir `{parent_rel}/` doesn't exist"
        suggestion = (
            f"verify file path `{fc.path}` — parent dir "
            f"`{parent_rel}/` doesn't exist"
        )
        return (issue, suggestion)
    if fc.status == FileExistence.NEW and step_status == StepStatus.DONE:
        issue = f"`{fc.path}` missing on disk (step marked done)"
        return (issue, None)
    return ("", None)


def _render_path_style_section(hint: PathStyleHint) -> list[str]:
    """Render the top-level "Plan-wide path issue" markdown block as lines.

    Returns lines (not a single string) so the caller can extend its line
    buffer directly without an extra split.
    """
    pct = round(hint.ratio * 100)
    out: list[str] = []
    out.append("### Plan-wide path issue")
    out.append("")
    out.append(
        f"{hint.missing_count} of {hint.total} declared file paths don't "
        f"resolve under repo root `{hint.repo_root}` ({pct}% mismatch — "
        "likely a systemic prefix mismatch, not per-step bugs). Examples:"
    )
    out.append("")
    for example in hint.examples:
        out.append(f"- `{example}`")
    out.append("")
    out.append(
        "Try running with `--repo-root <other path>` or `--plans-dir <dir>` "
        "if the plan was authored against a different repo root."
    )
    out.append("")
    return out


def _render_completeness_section(
    body_issues: list[BodyCompletenessIssue],
    detail_coverage: list[DetailCoverageIssue],
    detail_body_issues: list[DetailBodyIssue],
    files_coherence_issues: list[FilesCoherenceIssue],
    lessons_issues: list[LessonsCoverageIssue],
    *,
    step_filter: Optional[int] = None,
) -> list[str]:
    """Render the "Plan completeness" markdown block as lines.

    Returns ``[]`` when every completeness check is empty so the
    section is elided rather than rendering an empty header.

    Renders AFTER correctness output by convention — caller positions
    this block between per-step status (correctness) and the claude
    review section.
    """
    # Filter to a single step when requested. Plan-wide findings (body
    # sections, lessons missing-file) are skipped under a step filter
    # since they're not step-scoped.
    def _step_match(step_id: Optional[int]) -> bool:
        if step_filter is None:
            return True
        return step_id == step_filter

    filtered_detail_cov = [
        i for i in detail_coverage if _step_match(i.step_id)
    ]
    filtered_detail_body = [
        i for i in detail_body_issues if _step_match(i.step_id)
    ]
    filtered_files_coh = [
        i for i in files_coherence_issues if _step_match(i.step_id)
    ]
    filtered_lessons = [
        i for i in lessons_issues if _step_match(i.step_id)
    ]
    filtered_body = body_issues if step_filter is None else []

    has_any = any(
        [
            filtered_body,
            filtered_detail_cov,
            filtered_detail_body,
            filtered_files_coh,
            filtered_lessons,
        ]
    )
    if not has_any:
        return []

    out: list[str] = []
    out.append("### Plan completeness")
    out.append("")
    if filtered_body:
        out.append("**Body sections**")
        out.append("")
        for issue in filtered_body:
            out.append(
                f"- {issue.kind.upper()}: `## {issue.section}` — {issue.details}"
            )
        out.append("")
    if filtered_detail_cov:
        out.append("**Detail coverage**")
        out.append("")
        for issue in filtered_detail_cov:
            if issue.kind == "unreferenced_on_disk":
                out.append(
                    f"- WARN: step {issue.step_id} detail "
                    f"`{issue.detail_path}` on disk but unreferenced in "
                    "frontmatter"
                )
            else:
                out.append(
                    f"- WARN: step {issue.step_id} detail "
                    f"`{issue.detail_path}` declared but missing on disk"
                )
        out.append("")
    if filtered_detail_body:
        out.append("**Detail body completeness**")
        out.append("")
        for issue in filtered_detail_body:
            verb = "missing" if issue.kind == "missing" else "is empty/placeholder"
            out.append(
                f"- WARN: step {issue.step_id} `{issue.detail_path}` — "
                f"`## {issue.section}` {verb}"
            )
        out.append("")
    if filtered_files_coh:
        # detail_only findings are individually low-signal and tend to come
        # in bunches, so collapse them under one counted header with terse
        # `cited ≈ declared` sub-bullets instead of a verbose INFO line each.
        detail_only = [
            i for i in filtered_files_coh if i.kind == "detail_only"
        ]
        nits = [i for i in filtered_files_coh if i.kind != "detail_only"]
        out.append("**Files coherence**")
        out.append("")
        if detail_only:
            steps = ", ".join(
                str(s) for s in sorted({i.step_id for i in detail_only})
            )
            out.append(
                f"- INFO: {len(detail_only)} detail path(s) resemble a "
                f"declared path (possible typo/stale ref; steps {steps})"
            )
            for issue in detail_only:
                out.append(
                    f"    - step {issue.step_id}: `{issue.path}` ≈ "
                    f"`{issue.near_match}`"
                )
        for issue in nits:
            out.append(
                f"- NIT: step {issue.step_id} declared "
                f"`{issue.path}` not mentioned in detail"
            )
        out.append("")
    if filtered_lessons:
        out.append("**Lessons coverage**")
        out.append("")
        for issue in filtered_lessons:
            if issue.kind == "missing_file":
                out.append(
                    f"- WARN: lessons file `{issue.lessons_path}` "
                    "missing but plan has done steps"
                )
            else:
                out.append(
                    f"- WARN: step {issue.step_id} done but no entry "
                    f"in `{issue.lessons_path}`"
                )
        out.append("")
    return out


def _render_severity_banner(recs: Sequence[Recommendation]) -> str:
    """Return a one-line severity histogram of the report's findings.

    Counts ``rec.severity`` directly, so the tally reuses the same severity
    constants every ``_*_recommendation`` builder already stamped
    (``_FILE_CHECK_MISSING_PARENT_SEV``, ``_HEURISTIC_HIT_SEV``, the
    ``_DEP_*_SEV`` / completeness ``_*_SEV`` constants, and
    ``_CLAUDE_SEVERITY_MAP``) — no parallel severity scheme. Levels render in
    ``_SEVERITY_BANNER_ORDER`` (most urgent first); zero-count levels are
    dropped to keep the line short. Any severity outside the order tuple
    (defensive — none expected) trails the known levels in insertion order so
    an unknown value still surfaces. An empty list renders ``Findings: none``.
    """
    counts = Counter(r.severity for r in recs)
    ordered = [lvl for lvl in _SEVERITY_BANNER_ORDER if lvl in counts]
    ordered += [lvl for lvl in counts if lvl not in _SEVERITY_BANNER_ORDER]
    parts = [f"{counts[lvl]} {lvl}" for lvl in ordered]
    return "Findings: " + (" · ".join(parts) if parts else "none")


def assemble_report(
    plan: Plan,
    plan_name: str,
    *,
    repo_root: Path,
    file_checks: list[StepFileCheck],
    heuristic_hits: list[HeuristicHit],
    dep_issues: list[DepIssue],
    claude_review: Optional[str],
    claude_note: Optional[str] = None,
    step_filter: Optional[int] = None,
    path_style_hint: Optional[PathStyleHint] = None,
    body_completeness: Optional[list[BodyCompletenessIssue]] = None,
    detail_coverage: Optional[list[DetailCoverageIssue]] = None,
    detail_body: Optional[list[DetailBodyIssue]] = None,
    files_coherence: Optional[list[FilesCoherenceIssue]] = None,
    lessons_coverage: Optional[list[LessonsCoverageIssue]] = None,
    recommendations: Optional[Sequence[Recommendation]] = None,
    walk_will_run: bool = False,
) -> str:
    """Format deterministic results + optional Claude section into a markdown report.

    ``claude_note`` is used when ``claude_review`` is None to explain why the
    Claude section is absent (e.g. executable missing, invoker disabled).

    ``path_style_hint`` (when provided) renders a top-level "Plan-wide path
    issue" section above per-step status. Per-step warnings still render
    unchanged — the hint is additive.

    ``recommendations`` (when provided) emits a one-line ``Findings:``
    severity histogram under the ``Repo root:`` header, tallying the
    already-built findings by ``rec.severity`` (see
    :func:`_render_severity_banner`). Semantic-review prose isn't tallied —
    it leads the report below. Default ``None`` omits the banner entirely so
    direct callers stay byte-identical.

    ``repo_root`` is used to resolve absolute paths for per-file diagnostic
    text via :func:`_describe_file_check`.

    ``walk_will_run`` says an interactive recommendation walk will follow
    this report and present every deterministic finding's detail itself.
    When ``True`` the report avoids restating that detail: the
    ``### Suggested actions`` block is omitted, per-step ``WARN`` lines
    collapse to a finding *count* (the OK/WARN map stays as the
    at-a-glance overview), and the ``> hint:`` legend is dropped (no
    inline ``hint:`` detail remains for it to explain). When ``False``
    (the default, and every non-interactive run) the report is the
    reader's only actionable surface, so the full block, full ``WARN``
    detail, and the severity banner's ``Finding:`` lines are all retained.
    The semantic review, completeness, and path-style sections render
    identically in both modes.
    """
    hits_by_step: dict[int, list[HeuristicHit]] = {}
    for h in heuristic_hits:
        hits_by_step.setdefault(h.step_id, []).append(h)
    deps_by_step: dict[int, list[DepIssue]] = {}
    for d in dep_issues:
        deps_by_step.setdefault(d.step_id, []).append(d)
    files_by_step = {fc.step_id: fc for fc in file_checks}

    lines: list[str] = []
    lines.append(f"## Plan Review: {plan.title}")
    lines.append("")
    lines.append(
        f"Metadata: status={plan.status.value} · priority={plan.priority.value} "
        f"· {len(plan.steps)} steps"
    )
    # Repo root is named once here; every per-finding line below stays
    # repo-relative so the absolute prefix isn't repeated on every WARN.
    lines.append(f"Repo root: `{repo_root}`")
    # At-a-glance severity histogram of the findings this report surfaces.
    # Part of the header block (under Repo root), so callers that pass no
    # ``recommendations`` stay byte-identical to the prior output.
    if recommendations is not None:
        lines.append(_render_severity_banner(recommendations))
        if not walk_will_run:
            for rec in recommendations:
                step = f" · step {rec.step_id}" if rec.step_id is not None else ""
                lines.append(
                    f"Finding: {rec.source}/{rec.severity}{step} "
                    f"[{confidence_label(rec.confidence)}] — {rec.title.strip()}"
                )
    lines.append("")

    # Claude's semantic review leads: it's the highest-signal section (real
    # bugs, reality checks), so it sits above the deterministic/heuristic
    # noise rather than being buried beneath it.
    lines.append("### Claude's semantic review")
    lines.append("")
    if claude_review is None:
        note = claude_note or (
            "Claude review not available (executable not found or skipped)."
        )
        lines.append(f"_{note}_")
    elif not claude_review.strip():
        lines.append("_Claude returned an empty response._")
    else:
        lines.append(claude_review.strip())
    lines.append("")

    if path_style_hint is not None:
        lines.extend(_render_path_style_section(path_style_hint))
    lines.append("### Per-step status")
    lines.append("")

    suggestions: list[str] = []
    any_heuristic = False

    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue

        file_check = files_by_step.get(step.id)
        step_hits = hits_by_step.get(step.id, [])
        step_dep_issues = deps_by_step.get(step.id, [])
        files_block = file_check.files if file_check else []

        issues: list[str] = []
        for fc in files_block:
            issue_text, suggestion_body = _describe_file_check(
                fc, step_status=step.status
            )
            if not issue_text:
                continue
            issues.append(issue_text)
            if suggestion_body is not None:
                suggestions.append(f"Step {step.id}: {suggestion_body}")
            elif (
                fc.status != FileExistence.OK
                and step.status == StepStatus.DONE
            ):
                # Missing-on-DONE (a NEW `files:` entry or a still-absent
                # `creates:` entry): the helper returns issue text but no
                # suggestion body, since reconcile guidance needs plan_name
                # and step.id which live in the caller's scope.
                suggestions.append(
                    f"Step {step.id}: run `plan-tool detail {plan_name} "
                    f"--reconcile --step {step.id}` to confirm"
                )
        for h in step_hits:
            any_heuristic = True
            issues.append(
                f"hint: symbol `{h.symbol}` already in `{h.file}`"
            )
            suggestions.append(
                f"Step {step.id}: run `plan-tool detail {plan_name} "
                f"--reconcile --step {step.id}` to confirm"
            )
        for d in step_dep_issues:
            issues.append(
                f"depends on step {d.depends_on} which is {d.reason}"
            )

        if issues:
            verdict = "WARN"
            if walk_will_run:
                # The walk presents each finding's detail interactively, so
                # the status line keeps only the count — detail lives in the
                # walk, not here.
                n = len(issues)
                detail = f"{n} finding{'s' if n != 1 else ''}"
            else:
                detail = "; ".join(issues)
        else:
            n_exist = sum(1 for fc in files_block if fc.status == FileExistence.OK)
            # In the no-issues branch every non-OK file is an expected
            # creation (a NEW `files:` entry on a pending step, or a
            # not-yet-landed `creates:` entry) — a non-created
            # MISSING_PARENT would have produced a WARN above.
            n_new = sum(1 for fc in files_block if fc.status != FileExistence.OK)
            n_total = len(files_block)
            if n_total == 0:
                detail = "no files declared"
            elif n_new == 0:
                detail = f"{n_exist} file(s) declared, all exist"
            elif n_exist == 0:
                detail = f"{n_new} file(s) to be created"
            else:
                detail = f"{n_exist} existing, {n_new} to be created"
            verdict = "OK"

        lines.append(
            f"- Step {step.id} ({step.status.value})  {verdict} — {detail}"
        )

    if any_heuristic and not walk_will_run:
        lines.append("")
        lines.append(
            "> `hint:` lines are low-confidence — a step's title shares a "
            "token with existing code, which may mean prior implementation "
            "or just a coincidental name collision. Don't change a step's "
            "`status` on a hint alone; run the suggested reconcile to confirm."
        )

    lines.append("")

    # Completeness checks render AFTER per-step status. The semantic review
    # has already led the report. Section is elided when every completeness
    # check is empty.
    completeness_lines = _render_completeness_section(
        body_completeness or [],
        detail_coverage or [],
        detail_body or [],
        files_coherence or [],
        lessons_coverage or [],
        step_filter=step_filter,
    )
    if completeness_lines:
        lines.extend(completeness_lines)

    if suggestions and not walk_will_run:
        lines.append("### Suggested actions")
        lines.append("")
        seen: set[str] = set()
        for s in suggestions:
            if s in seen:
                continue
            seen.add(s)
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)


def extract_recommendations(
    plan: Plan,
    plan_name: str,
    *,
    repo_root: Path,
    file_checks: list[StepFileCheck],
    heuristic_hits: list[HeuristicHit],
    dep_issues: list[DepIssue],
    path_style_hint: Optional[PathStyleHint],
    claude_stdout: Optional[str] = None,
    step_filter: Optional[int] = None,
    body_completeness: Optional[list[BodyCompletenessIssue]] = None,
    detail_coverage: Optional[list[DetailCoverageIssue]] = None,
    detail_body: Optional[list[DetailBodyIssue]] = None,
    files_coherence: Optional[list[FilesCoherenceIssue]] = None,
    lessons_coverage: Optional[list[LessonsCoverageIssue]] = None,
    input_contract_references: Optional[list[object]] = None,
    reconcile_lane: bool = False,
    granularity_recommendations: Optional[list[Recommendation]] = None,
    plan_path: Optional[Path] = None,
) -> list[Recommendation]:
    """Build a flat, walk-friendly list of ``Recommendation`` items.

    Mirrors the per-step iteration in :func:`assemble_report` so the
    structured output matches the markdown body shown to the user. The
    deterministic primitives (file_checks, heuristic_hits, dep_issues,
    path_style_hint) are required; completeness primitives and
    ``claude_stdout`` are optional.

    Iteration order is load-bearing for the walk feature — the user
    sees:

      1. plan-wide correctness (path-style)
      2. per-step correctness (file checks, heuristic, deps), grouped by step
      2a. plan-wide re-ground (reconcile lane only): one ``granularity-merge``
          finding when ≥2 distinct steps look already-built in code
      2b. pairwise merge (reconcile lane only): the deterministic
          ``granularity-merge`` findings the granularity advisor emits for
          dependency-adjacent step pairs, passed in via
          ``granularity_recommendations``
      2c. code-grounded split (reconcile lane only): one advisory ``info``
          ``granularity-split`` finding per non-``DONE`` step whose hits reveal
          a built part (≥2 distinct files) alongside an un-built non-test part
          (the inverse of the 2a re-ground finding)
      3. plan-wide completeness (body sections, lessons missing-file)
      4. per-step completeness (detail coverage, body, files coherence,
         lessons missing-entry)
      5. claude's findings

    Correctness ALWAYS precedes completeness so users address structural
    blockers before authoring gaps.

    ``reconcile_lane`` gates the 2a re-ground emit to the reconcile surface
    (``review_plan_full`` passes ``True``); the shared completeness /
    run-gate fan-out leaves it ``False`` so the plan-wide ≥2-step finding
    never reaches ``apply_finding`` or a non-reconcile report. The 2b pairwise
    merge findings from ``granularity_recommendations`` follow the same gate:
    they are appended only on the full-plan reconcile lane
    (``reconcile_lane and step_filter is None``), so a default helper call or a
    single-step reconcile run never surfaces them. The 2c code-grounded split
    findings share that gate. Split and re-ground are mutually exclusive: a
    split-qualifying step (partially built) is dropped from re-ground's input
    and from any pairwise-merge pair, so it is offered as a split only, never
    for "mark done" / merge. Producer fields (``id``, ``severity``,
    ``suggested_action``, …) pass through unchanged — this function selects, it
    does not rebuild.
    """
    recs: list[Recommendation] = []

    # 1. Plan-wide correctness.
    if path_style_hint is not None:
        recs.append(_path_style_recommendation(path_style_hint))

    by_step_files = {fc.step_id: fc for fc in file_checks}
    hits_by_step: dict[int, list[HeuristicHit]] = {}
    for h in heuristic_hits:
        hits_by_step.setdefault(h.step_id, []).append(h)
    deps_by_step: dict[int, list[DepIssue]] = {}
    for d in dep_issues:
        deps_by_step.setdefault(d.step_id, []).append(d)

    # 2. Per-step correctness.
    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        for fc in (by_step_files.get(step.id).files if step.id in by_step_files else []):
            rec = _file_check_recommendation(
                fc, step, plan_name=plan_name
            )
            if rec is not None:
                recs.append(rec)
        for hit in hits_by_step.get(step.id, []):
            recs.append(
                _heuristic_recommendation(hit, plan_name=plan_name)
            )
        for dep in deps_by_step.get(step.id, []):
            recs.append(_dep_recommendation(dep))

    # 2a. Plan-wide re-ground (reconcile lane only). Fires once when the
    # code already implements ≥2 distinct steps. The ``step_filter is None``
    # guard mirrors section 3: a single-step reconcile must not surface a
    # plan-wide set finding.
    if reconcile_lane and step_filter is None:
        # Re-ground reads the FULL hit set. The code-grounded split finding
        # (below) is a standalone *advisory* and must not filter re-ground's
        # input: the split trigger is a low-confidence built/un-built proxy, so a
        # false-positive split would otherwise suppress the higher-confidence
        # plan-wide re-baseline signal (drop it below its ≥2-step threshold).
        # Both are advisory ``info``; when they overlap on a step the operator
        # weighs them — the detector never couples to or mutates re-ground.
        reground = _reground_already_built_recommendation(
            heuristic_hits, plan_name=plan_name
        )
        if reground is not None:
            recs.append(reground)

        # Code-grounded split producer (the inverse of re-ground): a single step
        # whose hits reveal a built part + an un-built non-test part. Purely
        # additive — it filters neither the re-ground (2a) nor the pairwise-merge
        # (2b) findings.
        split_recs = _code_reveals_split_recommendations(
            hits_by_step, plan, plan_name=plan_name
        )
        # Best-effort telemetry: record each fire so #117's "is this
        # low-confidence signal worth keeping?" is answered from data, not a
        # manual study. Only fires here (reconcile lane, plan-wide) and only
        # when non-empty, so it stays low-noise.
        if split_recs:
            # Best-effort fingerprints so the event joins on the renumber-proof
            # anchor. Code-grounded, so telemetry carries its compact digest;
            # both computes are wrapped so a fingerprint error never perturbs the
            # host command. plan_path is None on the non-reconcile caller.
            plan_fp = ""
            code_state = ""
            if plan_path is not None:
                try:
                    from plan_tool.fingerprint import compute_code_fingerprint
                    from plan_tool.review_persistence import (
                        compute_plan_fingerprint,
                    )

                    plan_fp = compute_plan_fingerprint(plan_path)
                    code_state = code_fingerprint_digest(
                        compute_code_fingerprint(plan, plan_path, repo_root)
                    )
                except Exception:
                    plan_fp = ""
                    code_state = ""
            try:
                record_code_reveals_split(
                    repo_root,
                    plan_slug=plan_name,
                    steps=len(plan.steps),
                    step_ids=[str(r.step_id) for r in split_recs],
                    plan_fingerprint=plan_fp,
                    code_fingerprint=code_state,
                )
            except Exception:
                # Telemetry is observational even when tests or integrations
                # replace the convenience recorder with a raising callable.
                pass

        # 2b. Pairwise merge findings from the granularity advisor. Include only
        # the per-pair ``granularity-merge`` items (``step_id`` set); the
        # plan-wide re-ground finding (``step_id is None``) stays owned by
        # section 2a above. Same predicate the walk's visibility carve keys on,
        # so producer and carve can't drift. Passed through unfiltered — the
        # code-grounded split advisory does not suppress the static advisor's
        # merge (a different, structural lens); the two can honestly diverge and
        # a human resolves, and the split trigger is too low-confidence to gate a
        # visible finding on.
        for rec in granularity_recommendations or []:
            if is_pairwise_merge_finding(rec):
                recs.append(rec)

        recs.extend(split_recs)

    # 3. Plan-wide completeness.
    if step_filter is None:
        for issue in body_completeness or []:
            recs.append(_body_completeness_recommendation(issue))
        for issue in lessons_coverage or []:
            if issue.kind == "missing_file":
                recs.append(_lessons_recommendation(issue, plan_name=plan_name))
        for issue in input_contract_references or []:
            if getattr(issue, "step_id", None) is None:
                recs.append(_input_contract_reference_recommendation(issue))

    # 4. Per-step completeness, grouped by step.
    detail_cov_by_step: dict[int, list[DetailCoverageIssue]] = {}
    for issue in detail_coverage or []:
        detail_cov_by_step.setdefault(issue.step_id, []).append(issue)
    detail_body_by_step: dict[int, list[DetailBodyIssue]] = {}
    for issue in detail_body or []:
        detail_body_by_step.setdefault(issue.step_id, []).append(issue)
    files_coh_by_step: dict[int, list[FilesCoherenceIssue]] = {}
    for issue in files_coherence or []:
        files_coh_by_step.setdefault(issue.step_id, []).append(issue)
    lessons_entry_by_step: dict[int, list[LessonsCoverageIssue]] = {}
    for issue in lessons_coverage or []:
        if issue.kind == "missing_entry" and issue.step_id is not None:
            lessons_entry_by_step.setdefault(issue.step_id, []).append(issue)

    for step in plan.steps:
        if step_filter is not None and step.id != step_filter:
            continue
        for issue in detail_cov_by_step.get(step.id, []):
            recs.append(_detail_coverage_recommendation(issue, plan_name=plan_name))
        for issue in detail_body_by_step.get(step.id, []):
            recs.append(_detail_body_recommendation(issue, plan_name=plan_name))
        for issue in files_coh_by_step.get(step.id, []):
            recs.append(_files_coherence_recommendation(issue))
        for issue in lessons_entry_by_step.get(step.id, []):
            recs.append(_lessons_recommendation(issue, plan_name=plan_name))
        for issue in input_contract_references or []:
            if getattr(issue, "step_id", None) == step.id:
                recs.append(_input_contract_reference_recommendation(issue))

    # 5. Claude findings (last; semantic, may overlap with deterministic).
    if claude_stdout is not None:
        recs.extend(_claude_recommendations(claude_stdout))

    return recs


def _body_completeness_recommendation(
    issue: BodyCompletenessIssue,
) -> Recommendation:
    # Lazy-import the shape map to keep the module dependency graph a
    # tree (review.py already lazy-imports PLAN_BODY_SECTIONS from
    # create.py for the same reason).
    from plan_tool.create import PLAN_BODY_SECTION_SHAPES

    title = (
        f"Plan body section `## {issue.section}` "
        + ("missing" if issue.kind == "missing" else "is a placeholder")
    )
    # Embed the recommended content shape into the finding body so
    # apply_finding has concrete authoring guidance, not just
    # "this section is empty." Without the shape, claude reasonably
    # refuses placeholder findings as "too vague to act on without
    # guessing content" (observed during bug #24 verification: 8 of 11
    # placeholder findings refused with that exact reason). Sections
    # absent from the shape map (e.g. a custom required-section list
    # passed to check_body_completeness) fall back to issue.details
    # alone, preserving the legacy behavior.
    shape = PLAN_BODY_SECTION_SHAPES.get(issue.section)
    if shape:
        body = f"{issue.details}\n\nRecommended content shape: {shape}"
    else:
        body = issue.details
    suggested = (
        f"fill in the `## {issue.section}` section, or add "
        f"`<!-- completeness:skip {issue.section} -->` to suppress"
    )
    return Recommendation(
        id=_make_rec_id(None, "body-completeness", issue.section + issue.kind),
        source="body-completeness",
        severity=_BODY_COMPLETENESS_SEV,
        step_id=None,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _detail_coverage_recommendation(
    issue: DetailCoverageIssue, *, plan_name: str
) -> Recommendation:
    if issue.kind == "unreferenced_on_disk":
        title = f"Step {issue.step_id}: detail file on disk but unreferenced"
        body = (
            f"A detail file `{issue.detail_path}` exists for step "
            f"{issue.step_id}, but the step has no `detail:` pointer — so "
            "the launcher won't load it into the step's subprocess. The "
            "pointer was likely never persisted (e.g. a split that "
            "renumbered a step whose pointer was already unset)."
        )
        # No --force: the adoption pre-pass reattaches the canonical file
        # without re-authoring it.
        suggested = f"plan-tool detail {plan_name} --step {issue.step_id}"
        sev = _DETAIL_UNREFERENCED_ON_DISK_SEV
        return Recommendation(
            id=_make_rec_id(
                issue.step_id,
                "detail-coverage",
                issue.kind + (issue.detail_path or ""),
            ),
            source="detail-coverage",
            severity=sev,
            step_id=issue.step_id,
            title=title,
            body=body,
            suggested_action=suggested,
        )
    title = f"Step {issue.step_id}: detail file missing on disk"
    body = (
        f"Step {issue.step_id} declares `detail: {issue.detail_path}` "
        "but the file isn't present under the repo root."
    )
    suggested = (
        f"plan-tool detail {plan_name} --step {issue.step_id} --force"
    )
    sev = _DETAIL_MISSING_ON_DISK_SEV
    return Recommendation(
        id=_make_rec_id(
            issue.step_id, "detail-coverage", issue.kind + (issue.detail_path or "")
        ),
        source="detail-coverage",
        severity=sev,
        step_id=issue.step_id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _detail_body_recommendation(
    issue: DetailBodyIssue, *, plan_name: str
) -> Recommendation:
    title = (
        f"Step {issue.step_id}: detail `## {issue.section}` "
        + ("missing" if issue.kind == "missing" else "empty/placeholder")
    )
    body = (
        f"`{issue.detail_path}` lacks a populated `## {issue.section}` "
        "section. Required tokens: Why / Files / Implementation / "
        "Tests / Acceptance criteria."
    )
    suggested = (
        f"plan-tool detail {plan_name} --step {issue.step_id} --force"
    )
    return Recommendation(
        id=_make_rec_id(
            issue.step_id, "detail-body", issue.section + issue.kind
        ),
        source="detail-body",
        severity=_DETAIL_BODY_INCOMPLETE_SEV,
        step_id=issue.step_id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _files_coherence_recommendation(
    issue: FilesCoherenceIssue,
) -> Recommendation:
    if issue.kind == "detail_only":
        near = issue.near_match
        title = (
            f"Step {issue.step_id}: detail cites `{issue.path}` "
            f"resembling declared `{near}`"
        )
        body = (
            f"The detail body for step {issue.step_id} cites "
            f"`{issue.path}`, which isn't in the step's `files:` array "
            f"but closely resembles the declared `{near}`. Likely a "
            "typo or a stale/moved path that drifted from the "
            "machine-readable manifest."
        )
        suggested = (
            f"if `{issue.path}` and `{near}` are the same file, fix the "
            "mismatch (correct the citation or update `files:`); if the "
            f"citation is intentional context, add `{issue.path}` to "
            f"step {issue.step_id}'s `allowed_mentions:`"
        )
        sev = _FILES_COHERENCE_DRIFT_SEV
    else:
        title = (
            f"Step {issue.step_id}: declared `{issue.path}` "
            "not mentioned in detail"
        )
        body = (
            f"`{issue.path}` is in step {issue.step_id}'s `files:` array "
            "but the detail body doesn't mention it. Low-confidence "
            "drift signal — files may be touched without explicit "
            "mention."
        )
        suggested = (
            f"mention `{issue.path}` in step {issue.step_id}'s detail "
            f"`## Implementation`, or drop it from `files:` if the step "
            f"doesn't touch it"
        )
        sev = _FILES_COHERENCE_NIT_SEV
    return Recommendation(
        id=_make_rec_id(
            issue.step_id, "files-coherence", issue.kind + issue.path
        ),
        source="files-coherence",
        severity=sev,
        step_id=issue.step_id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _lessons_recommendation(
    issue: LessonsCoverageIssue, *, plan_name: str
) -> Recommendation:
    if issue.kind == "missing_file":
        title = (
            f"Lessons file `{issue.lessons_path}` missing despite "
            "done steps"
        )
        body = (
            f"`{issue.lessons_path}` is configured on the plan but the "
            "file doesn't exist on disk, while at least one step is "
            "marked done. Either the file was deleted, or done steps "
            "landed via a path that didn't call append_lesson."
        )
        suggested = (
            f"create `{issue.lessons_path}` and backfill entries for "
            "done steps, or unset `lessons:` on the plan"
        )
        sev = _LESSONS_MISSING_FILE_SEV
        step_id_for_rec: Optional[int] = None
    else:
        title = (
            f"Step {issue.step_id}: done but no lessons entry"
        )
        body = (
            f"Step {issue.step_id} is marked done but no line in "
            f"`{issue.lessons_path}` references its id. Directly edited "
            "frontmatter or pre-gates runs are the usual cause."
        )
        suggested = (
            f"add an entry naming `step {issue.step_id}:` to "
            f"`{issue.lessons_path}`, or run `plan-tool detail "
            f"{plan_name} --reconcile --step {issue.step_id}` "
            "to confirm delivery"
        )
        sev = _LESSONS_MISSING_ENTRY_SEV
        step_id_for_rec = issue.step_id
    return Recommendation(
        id=_make_rec_id(
            step_id_for_rec, "lessons-coverage", issue.kind + (issue.lessons_path or "")
        ),
        source="lessons-coverage",
        severity=sev,
        step_id=step_id_for_rec,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _input_contract_reference_recommendation(issue: object) -> Recommendation:
    # Deliberately stays at the confidence default despite sharing the
    # "data-contract" source below — see recommendation-confidence step 1
    # detail, "Source-name collision".
    owner = getattr(issue, "owner", None)
    field_or_key = getattr(issue, "field_or_key", None)
    code_anchor = getattr(issue, "code_anchor", None)
    location = getattr(issue, "location", "## Input")
    reason = getattr(issue, "reason", "stale Input contract reference")
    step_id = getattr(issue, "step_id", None)
    reference = code_anchor or (
        f"{owner}.{field_or_key}" if owner and field_or_key else "contract reference"
    )
    title = f"Stale Input contract reference `{reference}`"
    body = f"{location} cites `{reference}`, but {reason}."
    payload = {
        "target": "plan-detail",
        "location": location,
        "owner": owner,
        "field_or_key": field_or_key,
        "code_anchor": code_anchor,
        "reason": reason,
        "step_id": step_id,
    }
    fingerprint = json.dumps(payload, sort_keys=True)
    anchor_ref = reference.lower().replace("/", "-").replace(".", "-")
    anchor_ref = re.sub(r"[^a-z0-9:-]+", "-", anchor_ref).strip("-")
    return Recommendation(
        id=_make_rec_id(step_id, "data-contract", fingerprint),
        source="data-contract",
        severity="medium",
        step_id=step_id,
        title=title,
        body=body,
        suggested_action=(
            "Update the plan/detail `## Input` reference to match HEAD, "
            "or remove it if this step no longer consumes that contract."
        ),
        anchor=f"data-contract-input-{anchor_ref}",
    )


def _make_rec_id(
    step_id: Optional[int], source: str, fingerprint: str
) -> str:
    """Build a stable id from the step id, source, and a content fingerprint.

    SHA-256 truncated to 8 hex chars is plenty for collision resistance
    within a single saved review (a few dozen items at most). The
    ``step{N}`` / ``plan`` prefix keeps ids human-readable when they
    appear in CLI output (e.g., ``reconcile-plan-walk --start step3-deps-1a2b3c4d``).
    """
    h = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:8]
    step_str = f"step{step_id}" if step_id is not None else "plan"
    return f"{step_str}-{source}-{h}"


def _path_style_recommendation(hint: PathStyleHint) -> Recommendation:
    pct = round(hint.ratio * 100)
    body = (
        f"{hint.missing_count} of {hint.total} declared file paths "
        f"don't resolve under repo root `{hint.repo_root}` "
        f"({pct}% mismatch). Examples: "
        + ", ".join(f"`{p}`" for p in hint.examples)
    )
    suggested = (
        "re-run with `--repo-root <correct-path>` if the plan was "
        "authored against a different repo root"
    )
    return Recommendation(
        id=_make_rec_id(None, "path-style", body),
        source="path-style",
        severity=_PATH_STYLE_SEV,
        step_id=None,
        title=f"Plan-wide path issue ({pct}% paths don't resolve)",
        body=body,
        suggested_action=suggested,
    )


def _file_check_recommendation(
    fc: FileCheck,
    step: Step,
    *,
    plan_name: str,
) -> Optional[Recommendation]:
    """Build a Recommendation for a problematic FileCheck, or None for OK files.

    Paths in the body are repo-relative (the string the user wrote in the
    plan), matching the markdown report — the absolute repo root is not
    repeated per finding.

    Files declared under ``creates:`` (``fc.created``) are expected to be
    absent until the step runs, so they never produce the MISSING_PARENT
    "doesn't resolve" finding. The one exception is a DONE step whose
    created file never landed — surfaced as a missing-despite-done finding.
    """
    parent_rel = Path(fc.path).parent
    if fc.created:
        if fc.status != FileExistence.OK and step.status == StepStatus.DONE:
            title = (
                f"Step {step.id}: created file missing despite step marked done"
            )
            body = (
                f"`{fc.path}` is declared under `creates:` but isn't on "
                f"disk although step {step.id} is marked `done`"
            )
            suggested = (
                f"run `plan-tool detail {plan_name} --reconcile "
                f"--step {step.id}` to confirm whether the work landed"
            )
            return Recommendation(
                id=_make_rec_id(step.id, "file-check", body),
                source="file-check",
                severity=_FILE_CHECK_NEW_ON_DONE_SEV,
                step_id=step.id,
                title=title,
                body=body,
                suggested_action=suggested,
                confidence="supported",
            )
        return None
    if fc.status == FileExistence.MISSING_PARENT:
        title = f"Step {step.id}: declared file path doesn't resolve"
        body = f"`{fc.path}` — parent dir `{parent_rel}/` doesn't exist"
        suggested = (
            f"verify the path or pass `--allow-missing-parent` if the "
            f"step legitimately creates `{fc.path}`"
        )
        return Recommendation(
            id=_make_rec_id(step.id, "file-check", body),
            source="file-check",
            severity=_FILE_CHECK_MISSING_PARENT_SEV,
            step_id=step.id,
            title=title,
            body=body,
            suggested_action=suggested,
            file_path=fc.path,
            confidence="supported",
        )
    if fc.status == FileExistence.NEW and step.status == StepStatus.DONE:
        title = f"Step {step.id}: declared file missing despite step marked done"
        body = (
            f"`{fc.path}` missing on disk although step {step.id} is "
            "marked `done`"
        )
        suggested = (
            f"run `plan-tool detail {plan_name} --reconcile "
            f"--step {step.id}` to confirm whether the work landed"
        )
        return Recommendation(
            id=_make_rec_id(step.id, "file-check", body),
            source="file-check",
            severity=_FILE_CHECK_NEW_ON_DONE_SEV,
            step_id=step.id,
            title=title,
            body=body,
            suggested_action=suggested,
            confidence="supported",
        )
    return None


def _heuristic_recommendation(
    hit: HeuristicHit, *, plan_name: str
) -> Recommendation:
    title = (
        f"Step {hit.step_id} [low-confidence hint]: title symbol "
        f"`{hit.symbol}` found in `{hit.file}` — possible prior "
        "implementation"
    )
    body = (
        f"Heuristic matched pattern `{hit.pattern}` (token `{hit.symbol}`) "
        f"in `{hit.file}` — possible prior implementation or a coincidental "
        "token collision. Not a status verdict; confirm with the suggested "
        "reconcile before changing `status`."
    )
    suggested = (
        f"run `plan-tool detail {plan_name} --reconcile "
        f"--step {hit.step_id}` to confirm"
    )
    return Recommendation(
        id=_make_rec_id(hit.step_id, "heuristic", body),
        source="heuristic",
        severity=_HEURISTIC_HIT_SEV,
        step_id=hit.step_id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _reground_already_built_recommendation(
    heuristic_hits: list[HeuristicHit], *, plan_name: str
) -> Optional[Recommendation]:
    """One plan-wide ``granularity-merge`` re-ground finding when the code
    already implements ≥2 distinct plan steps, else ``None``.

    The code-grounded sibling of ``granularity.py``'s plan-structure-only
    merge detectors: it reads the cross-step *set* of
    :func:`heuristic_already_done` hits (not one hit, like
    :func:`_heuristic_recommendation`) and fires only when ≥2 distinct
    ``step_id``s are flagged. Advisory, non-apply-eligible, plan-wide
    (``step_id=None``); the remedy is to re-ground the plan against HEAD,
    not an unconditional merge (the flagged steps may be non-adjacent or
    non-``PENDING``, which :func:`merge_steps` forbids).
    """
    # Distinct steps, not raw hits: heuristic_already_done appends one hit
    # per (step, file), so a single step can produce several.
    step_ids = sorted({hit.step_id for hit in heuristic_hits})
    if len(step_ids) < 2:
        return None
    ids_str = ", ".join(str(i) for i in step_ids)
    fingerprint = "reground-already-built:" + ",".join(str(i) for i in step_ids)
    title = (
        f"Re-ground: steps {ids_str} appear already-built in code — "
        "re-baseline the plan against HEAD"
    )
    body = (
        f"{len(step_ids)} distinct steps ({ids_str}) have title symbols "
        "already present in their declared files per the "
        "`heuristic_already_done` scan, so the plan's decomposition looks "
        "stale relative to the code at HEAD. This is a low-confidence "
        "heuristic that can false-positive on superficial symbol overlap — "
        "confirm the steps really are built before re-baselining."
    )
    suggested = (
        f"re-baseline the set against HEAD: mark the already-built steps "
        f"`done`; if (and only if) they form a contiguous all-`PENDING` "
        f"run, `plan-tool merge` them, otherwise re-decompose via "
        f"`plan-tool create {plan_name} --from-existing <seed.md>`. "
        "Re-ground, not an unconditional merge. "
        + render_merge_action(MERGE_ACTION_REGROUND, step_ids)
    )
    return Recommendation(
        id=_make_rec_id(None, _GRANULARITY_MERGE_SOURCE, fingerprint),
        source=_GRANULARITY_MERGE_SOURCE,
        severity=_HEURISTIC_HIT_SEV,
        step_id=None,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _code_reveals_split_recommendations(
    hits_by_step: dict[int, list[HeuristicHit]], plan: Plan, *, plan_name: str
) -> list[Recommendation]:
    """One advisory ``granularity-split`` finding per non-``DONE`` step whose
    code reveals it fuses a built part and an un-built part.

    The code-grounded *inverse* of
    :func:`_reground_already_built_recommendation` (≥2 already-built *steps* →
    merge/re-ground). Here a *single* step is the unit: it qualifies when its
    :func:`heuristic_already_done` hits cover ≥2 distinct **non-test** files (a
    substantial built portion) while ≥1 declared ``files`` entry has no hit and
    at least one such un-hit file is a **scannable non-test** file (a real second
    concern, not tests trailing their feature and not an unscannable file the
    heuristic never opens). Non-test is applied to *both* sides symmetrically.
    That built/un-built co-occurrence is the signal the step spans two separable
    concerns and should split along the seam. **Purely additive / advisory**: it
    filters neither re-ground nor the pairwise-merge findings, so a false
    positive (the built/un-built proxy is low-confidence) never suppresses a
    higher-confidence signal — see BACKLOG for the signal-quality follow-up.

    Advisory ``info`` only: reuses the ``granularity-split`` literal so it routes
    through :func:`triage_reason`'s split branch pointing at ``plan-tool split``,
    but ``info`` (not ``medium``) keeps :func:`split_escalation_target` from ever
    auto-dispatching it. Reads only the existing hit list plus ``step.files`` —
    no new scanning; a hit's ``file`` is string-equal to the ``step.files`` entry
    it came from, so the un-built check is a plain set difference. Takes the
    ``hits_by_step`` map ``extract_recommendations`` already built (no rebuild).
    A ``DONE`` step never yields a finding — ``heuristic_already_done`` emits no
    hits for it, so it fails the ≥2-distinct-file test (the explicit status skip
    is belt-and-suspenders for a synthetic hit list, not the load-bearing gate).
    """
    recs: list[Recommendation] = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        # Count only NON-test files on the built side, symmetric with the
        # un-built guard below: hits on pre-written test files (a title symbol
        # like ``foo`` matching ``test_foo``) must not, on their own, make a step
        # look like it has a substantial "built part" — the built part we care
        # about is production code.
        built_files = {
            hit.file
            for hit in hits_by_step.get(step.id, [])
            if not _is_test_code_path(hit.file)
        }
        if len(built_files) < 2:
            continue
        # An un-hit declared file is a proxy for an un-built portion, but only a
        # *scannable* one is real evidence: ``heuristic_already_done`` never opens
        # an unscannable-extension file (e.g. ``.yaml``/``.sh``), so its absence
        # of a hit means "not scanned", not "un-built" — counting it would flag a
        # fully-built step. And only a *non-test* file is a separable second
        # concern (an un-built test alone is tests trailing a landed feature —
        # one half-done concern, not a split).
        unbuilt_non_test = [
            f
            for f in step.files
            if f not in built_files
            and _is_scannable_path(f)
            and not _is_test_code_path(f)
        ]
        if not unbuilt_non_test:
            continue
        recs.append(
            _code_reveals_split_recommendation(
                step, sorted(built_files), unbuilt_non_test, plan_name=plan_name
            )
        )
    return recs


def _code_reveals_split_recommendation(
    step: Step,
    built_files: list[str],
    unbuilt_non_test: list[str],
    *,
    plan_name: str,
) -> Recommendation:
    """The per-step ``granularity-split`` finding built by
    :func:`_code_reveals_split_recommendations`.

    Keyed on the *step* (``code-reveals-split:<step_id>``), not the volatile
    built-file set, so the id is stable across passes as more files get built —
    a prior ``skip`` annotation survives instead of re-nagging. Mirrors
    :func:`_reground_already_built_recommendation`, which keys only on its
    step-id set.
    """
    fingerprint = f"code-reveals-split:{step.id}"
    built_str = ", ".join(f"`{f}`" for f in built_files)
    unbuilt_str = ", ".join(f"`{f}`" for f in unbuilt_non_test)
    title = (
        f"Step {step.id}: code reveals a built/un-built split — split the "
        "already-implemented portion from the remainder"
    )
    body = (
        f"Step {step.id} looks partially built: title symbols already appear in "
        f"{len(built_files)} declared files ({built_str}) per the "
        f"`heuristic_already_done` scan, while these declared non-test files "
        f"have no hit and remain un-built: {unbuilt_str}. A single step "
        "spanning a built part and an un-built part usually fuses two separable "
        "concerns and should split along that seam. Caveats before splitting: "
        "(1) the built/un-built seam is a low-confidence proxy, not proof — "
        "confirm the step genuinely fuses two *separable* concerns, not one "
        "half-done concern; "
        "(2) `plan-tool split` leaves the first half at this step's status and "
        "later halves `pending`, so mark the built half `done` after splitting "
        "or `run` will re-implement the already-built code; "
        "(3) when several steps qualify, apply highest-id-first (or re-run "
        "reconcile between splits) — `plan-tool split` renumbers to contiguous "
        "ids, so splitting a lower-id step first invalidates the other "
        "`--step` numbers."
    )
    suggested = (
        f"split the built portion from the un-built portion: "
        f"`plan-tool split {plan_name} --step {step.id} "
        f'--into "..." --into "..."` (fill in the two half-titles)'
    )
    return Recommendation(
        id=_make_rec_id(step.id, "granularity-split", fingerprint),
        source="granularity-split",
        severity=_HEURISTIC_HIT_SEV,
        step_id=step.id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


def _dep_recommendation(dep: DepIssue) -> Recommendation:
    sev = _DEP_BLOCKED_SEV if dep.reason == "blocked" else _DEP_UNKNOWN_SEV
    title = (
        f"Step {dep.step_id}: depends on step {dep.depends_on} "
        f"which is {dep.reason}"
    )
    body = title
    suggested = (
        f"unblock or fix dependency on step {dep.depends_on} "
        f"before running step {dep.step_id}"
    )
    return Recommendation(
        id=_make_rec_id(dep.step_id, "deps", title),
        source="deps",
        severity=sev,
        step_id=dep.step_id,
        title=title,
        body=body,
        suggested_action=suggested,
        confidence="supported",
    )


# Reconcile producers whose findings carry a ``→ fix:`` one-line
# remediation, so :func:`extract_reconcile_recommendations` splits it onto
# ``suggested_action`` for the walk to display. ``detail-reconcile`` and
# ``run-reconcile`` adopted the plan-audit convention; plain ``reconcile``
# predates it and keeps its remediation inline in the body.
_RECONCILE_FIX_SOURCES: frozenset[str] = frozenset(
    {"detail-reconcile", "run-reconcile"}
)


def extract_reconcile_recommendations(
    stdout: str,
    *,
    step_id: int,
    source: str = "reconcile",
    parse_redirect: bool = False,
    parse_fix: Optional[bool] = None,
) -> list[Recommendation]:
    """Build Recommendations from a reconcile-mode claude response.

    Each finding bullet is turned into a Recommendation tagged with
    ``source`` (default ``"reconcile"``) and the audited ``step_id``
    so the walker can group findings under the right step. Bullets
    retain their severity (CRITICAL → critical, etc.).

    The reconcile prompt directs claude to phrase each finding as a
    plan edit (not a code change), so the rec's body is already
    actionable. The ``suggested_action`` is left ``None`` unless
    ``parse_fix`` is set (see below).

    Callers pass ``source="detail-reconcile"`` for the
    ``plan-tool detail --reconcile`` audit path so downstream
    review_walk routing keys off the producer (both sources land in
    the same ``_APPLY_AS_FINDING_SOURCES`` frozenset, so the apply
    dispatch is shared).

    ``parse_redirect=True`` enables per-bullet ``## Redirect``
    sub-block extraction — only the ``run-reconcile`` path sets this
    (reconcile and detail-reconcile recs never carry a redirect).

    ``parse_fix`` splits a trailing ``→ fix: <one-line remediation>`` off
    each bullet into ``suggested_action`` so the walk can render the
    proposed fix as a distinct line. Left ``None`` (the default) it is
    derived from ``source`` — on for the producers in
    :data:`_RECONCILE_FIX_SOURCES` (``detail-reconcile`` /
    ``run-reconcile``), off for plain ``reconcile`` — so every call site
    gets the right behavior without threading the flag. The fix is
    stripped from the body BEFORE the title and id are computed (so a
    reworded fix can't destabilize a finding's id), mirroring the
    plan-audit parser. Whether the rendered fix reads as "will apply"
    (and feeds ``apply_finding`` via :func:`audit_targeted_fix`) is a
    separate question keyed off :data:`AUDIT_FIX_SOURCES`:
    ``detail-reconcile`` is in it (its findings ARE applied as plan/detail
    edits), ``run-reconcile`` is not (its code edits already landed inline
    during the audit, so its fix stays a neutral "suggested" line).
    """
    from plan_tool.launcher import parse_finding_bullets

    if parse_fix is None:
        parse_fix = source in _RECONCILE_FIX_SOURCES
    bullets = parse_finding_bullets(stdout)
    out: list[Recommendation] = []
    for bullet in bullets:
        # Same misshape recovery as ``_parse_plan_audit_findings`` —
        # ``HIGH `[anchor]`: prose`` arrives UNSPECIFIED with the level
        # parked in the body; lift before the info default.
        raw_sev, body = _recover_severity_from_body(
            bullet.severity, bullet.body
        )
        sev = _CLAUDE_SEVERITY_MAP.get(raw_sev, "info")
        # Pull the inline ``(impact: …, complexity: …)`` pair the
        # reconcile prompts emit so the iteration loop can triage
        # applies. Stripped from the body before redirect parsing /
        # id minting so it doesn't leak into the finding text or the
        # rendered title. Untagged bullets fall open to apply.
        impact, complexity, body = _split_triage_tags(body)
        # A redirect and a trailing fix are mutually exclusive in the prompt
        # contract. Parse the redirect first so a malformed combined finding
        # retains the plan-owned signal instead of swallowing it as a fix
        # (see :func:`_split_audit_fix`'s docstring for the id-stability
        # ordering rule this also has to satisfy).
        redirect = parse_redirect_block(body) if parse_redirect else None
        # A present-but-field-empty match (parse_redirect_block's own
        # contract-miss leniency -- see its docstring) is too weak a signal
        # to let win over an actual trailing fix marker; only a redirect
        # with real content does.
        redirect_has_content = redirect is not None and bool(
            redirect.reason or redirect.suggested_next
        )
        fix: Optional[str] = None
        if parse_fix and redirect_has_content:
            heading = _find_redirect_heading(body)
            assert heading is not None  # redirect_has_content implies a match
            pre, post = body[: heading.start(1)], body[heading.start(1) :]
            discarded_fix, stripped_pre = _split_audit_fix(pre)
            if discarded_fix is not None:
                body = f"{stripped_pre.rstrip()}\n\n{post}"
        elif parse_fix:
            fix, body = _split_audit_fix(body)
        sev, _coerced = _enforce_high_impact_severity(
            sev,
            impact,
            severity_established=raw_sev != "UNSPECIFIED",
        )
        title = body.splitlines()[0][:120] if body else "(unspecified)"
        out.append(
            Recommendation(
                id=_make_rec_id(step_id, source, body),
                source=source,
                severity=sev,
                step_id=step_id,
                title=title,
                body=body,
                suggested_action=fix,
                redirect=redirect,
                impact=impact,
                complexity=complexity,
            )
        )
    return out


# Labelled-field regex factory shared by the Redirect parser (and any
# future per-finding sub-block parsers). Tolerates: leading bullet
# (``-`` / ``*``), optional bold (``**Reason**``), and ``:`` or ``-``
# separator. Whitespace is permissive on both sides so claude
# formatting drift (e.g. ``- **Reason** : foo``) doesn't break parsing.
def _labelled_field_re(label: str) -> "re.Pattern[str]":
    return re.compile(
        rf"^\s*(?:[-*]\s*)?(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[:\-]\s*(.+?)\s*$",
        re.MULTILINE,
    )


# run-reconcile.md's schema requires the heading to sit "immediately
# after the bullet (separated by a blank line)" -- require that blank-line
# paragraph break (or start-of-text) here too, not just a line start, so a
# ``→ fix:`` remediation that (in contract violation) wraps onto a new
# line starting with the same words isn't mistaken for a real sub-block.
# ``\r?`` tolerates CRLF text (cached/replayed payloads aren't guaranteed
# universal-newline-normalized the way a live subprocess capture is).
# Group 1 isolates the heading's own start from the leading alternation.
_REDIRECT_HEADING_RE = re.compile(r"(?:\A|\r?\n[ \t]*\r?\n)(##\s*Redirect\b)")
_REDIRECT_REASON_RE = _labelled_field_re("Reason")
_REDIRECT_SUGGESTED_NEXT_RE = _labelled_field_re("Suggested next")


def _find_redirect_heading(text: str) -> Optional[re.Match[str]]:
    """Locate the first ``## Redirect`` heading match outside any fenced
    span (mirroring :func:`_split_audit_fix`'s own fence exclusion) so a
    citation quoting this convention doesn't fake a real sub-block."""
    spans = fenced_spans(text)
    matches = _outside_fences(list(_REDIRECT_HEADING_RE.finditer(text)), spans)
    return matches[0] if matches else None


def parse_redirect_block(text: str) -> Optional[Redirect]:
    """Extract the ``## Redirect`` block from one run-reconcile finding's body.

    Returns ``None`` when no ``## Redirect`` heading is present in
    ``text`` — that's the common case (most findings carry no redirect
    because the code, not the plan, is the wrong piece). Callers branch
    on ``is not None`` to detect a redirect.

    When the heading is present, every field is best-effort: a missing
    or unparseable labelled line produces ``""``. An empty ``reason``
    on a present heading is a contract miss (claude emitted the heading
    but skipped the bullets); the parser still returns a ``Redirect``
    so the CLI surfaces the redirect with an ``(unspecified)`` filler
    rather than silently dropping the signal. The parser never raises
    on malformed input.

    Anchored to the *first* non-fenced ``## Redirect`` heading in ``text``
    that starts its own paragraph (see :func:`_find_redirect_heading`).
    The run-reconcile prompt's contract is one block per finding; if
    claude accidentally echoes two, the first wins.
    """
    heading = _find_redirect_heading(text)
    if heading is None:
        return None
    block = text[heading.end():]

    def _field(pat: "re.Pattern[str]") -> str:
        m = pat.search(block)
        return m.group(1).strip() if m else ""

    return Redirect(
        reason=_field(_REDIRECT_REASON_RE),
        suggested_next=_field(_REDIRECT_SUGGESTED_NEXT_RE),
    )


def extract_run_reconcile_recommendations(
    stdout: str, *, step_id: int
) -> list[Recommendation]:
    """Build Recommendations from a ``run-reconcile`` claude response.

    Thin wrapper over :func:`extract_reconcile_recommendations` with
    ``source="run-reconcile"`` (so ``_make_rec_id`` namespaces these
    recs separately) and ``parse_redirect=True`` (so the per-bullet
    ``## Redirect`` sub-block lands on each rec). The ``→ fix:`` split is
    auto-enabled by source (``run-reconcile`` ∈
    :data:`_RECONCILE_FIX_SOURCES`). Findings with a populated
    ``redirect`` are still emitted as recommendations; the CLI is
    responsible for branching on ``rec.redirect is not None`` to surface
    them as ``[REDIRECT]`` on stderr rather than running them through any
    apply path.
    """
    return extract_reconcile_recommendations(
        stdout,
        step_id=step_id,
        source="run-reconcile",
        parse_redirect=True,
    )


# Ordered severity for the triage gate's complexity-vs-impact
# comparison. ``"low" < "medium" < "high"``. Anything outside the
# enum (None, "", or unrecognized text) maps to ``-1`` so the gate
# treats it as "no signal; don't skip" -- conservative default
# preserves the legacy "apply everything" semantics for findings
# that don't carry triage tags (e.g. deterministic completeness
# checks, legacy reconcile output without Impact/Complexity).
_TRIAGE_LEVELS = {"low": 0, "medium": 1, "high": 2}


def _triage_level(value: Optional[str]) -> int:
    if not value:
        return -1
    return _TRIAGE_LEVELS.get(value.strip().lower(), -1)


# Finding sources whose remedy is a prose edit ``apply_finding`` can
# actually make -- writing a plan body section, filling a detail-file
# section, applying a conceptual-correctness fix, or landing a
# reconcile/claude-proposed plan edit. Every other source is a
# *structural diagnostic*: a declared path that doesn't resolve
# (``file-check`` / ``path-style``), a dependency-graph gap (``deps``),
# a step's declared detail file not on disk (``detail-coverage``), a
# detail/step.files coherence mismatch (``files-coherence``), or a
# lessons gap (``lessons-coverage``). ``apply_finding`` is a plan/detail
# prose editor -- it can't create a file, rewrite step.files frontmatter,
# or author a missing detail file -- so dispatching those just burns a
# claude call that comes back NOT-APPLICABLE. They're surfaced in the
# report (and the deferred summary) for the operator to resolve directly
# (fix the path, run ``plan-tool detail``, author lessons, ...).
APPLY_ELIGIBLE_SOURCES: frozenset[str] = frozenset(
    {
        "body-completeness",
        "detail-body",
        "plan-correctness",
        "reconcile",
        "detail-reconcile",
        "run-reconcile",
        "claude",
    }
)


def is_apply_eligible(rec: Recommendation) -> bool:
    """True when ``apply_finding`` can act on ``rec`` by editing plan or
    detail prose. False for structural diagnostics (see
    :data:`APPLY_ELIGIBLE_SOURCES`) that would only return
    NOT-APPLICABLE and waste a claude call."""
    return rec.source in APPLY_ELIGIBLE_SOURCES


# Sources whose only correct fix is to split a step into two type-pure
# steps, not an apply edit. Two producers:
#   - ``granularity-split`` — the live advisor source at HEAD
#     (``plan_tool/granularity.py``'s split detectors + the MIXED-STEP
#     purity kernel, surfaced through detail).
#   - ``structural-split`` — the escalate-to-split bridge's recommend-only
#     source (emitted when it declines to mutate structure: unattended /
#     unsafe / non-TTY). The producer lands in a later step; until then the
#     branch is forward-wiring, exercised only by synthetic recs in tests.
# Kept independent of APPLY_ELIGIBLE_SOURCES (a structural source is never
# apply-eligible) — the disjointness is pinned by test, not derived here.
#
# The "granularity-split" string is duplicated from
# ``granularity.GRANULARITY_SPLIT_SOURCE`` deliberately, NOT imported:
# ``granularity`` imports ``review`` (Recommendation/_make_rec_id), so the
# reverse import would cycle. Keep the literal in sync with that constant; a
# test pins the value so a future rename of the granularity source is caught.
STRUCTURAL_SOURCES: frozenset[str] = frozenset(
    {"granularity-split", "structural-split"}
)


# The reconcile lane's code-grounded re-ground finding (≥2 already-built
# steps) shares this source token with ``granularity.py``'s deterministic
# plan-structure-only merge detectors. The string is duplicated from
# ``granularity.GRANULARITY_MERGE_SOURCE``, NOT imported, for the same
# cycle reason as ``"granularity-split"`` above (granularity imports
# review). Deliberately absent from both APPLY_ELIGIBLE_SOURCES and
# STRUCTURAL_SOURCES: that omission is what makes ``is_apply_eligible`` and
# ``is_structural`` return False, so the finding rides the generic
# non-apply-eligible branch of ``triage_reason`` (made merge/re-ground-aware
# there), never the split bridge. A test pins this equal to the granularity
# constant so a future rename is caught.
_GRANULARITY_MERGE_SOURCE = "granularity-merge"


# --- machine-parseable merge/re-ground directive grammar -------------------
#
# The ``granularity-merge`` source is shared by two producers (see the
# comment on ``_GRANULARITY_MERGE_SOURCE`` above), so a consumer can't tell
# which remedy a finding wants — nor which steps it targets — from the source
# token alone: the plan-wide re-ground finding sets ``step_id=None`` and hides
# the id set inside its fingerprint, which ``_make_rec_id`` hashes. This
# grammar carries the remedy *kind* and the target step ids in a single
# machine marker appended to ``suggested_action`` — the re-ground analog of
# the split side's ``granularity.split_predicate_key``. ``render_merge_action``
# is the sole writer and ``parse_merge_action`` the sole reader, so the two
# can't drift. The grammar is kind-carrying (it defines and parses ``merge``
# too) so the deferred merge bridge follow-up extends it without rework; only
# the re-ground producer emits a directive in this plan.
MERGE_ACTION_MERGE = "merge"
MERGE_ACTION_REGROUND = "reground"

_MERGE_ACTION_MARKER_RE = re.compile(r"→\s*(merge|reground)\s+steps:\s*([0-9,\s]+)")


@dataclass(frozen=True)
class MergeAction:
    """Recovered ``(kind, step_ids)`` from a ``granularity-merge`` finding's
    directive marker. In-memory classification result only — never serialized
    (``suggested_action``'s field shape is unchanged)."""

    kind: str
    step_ids: tuple[int, ...]


def render_merge_action(kind: str, step_ids: Iterable[int]) -> str:
    """Render the single canonical directive marker for a merge/re-ground
    finding (e.g. ``→ reground steps: 3, 4, 5``). The producer appends this to
    its human prose; only :func:`parse_merge_action` reverses it, so the
    written marker and the parsed marker can't fork."""
    ids_str = ", ".join(str(i) for i in step_ids)
    return f"→ {kind} steps: {ids_str}"


def parse_merge_action(rec: Recommendation) -> Optional[MergeAction]:
    """Recover the ``(kind, step_ids)`` a ``granularity-merge`` finding
    targets, or ``None``.

    Keys on the machine marker written by :func:`render_merge_action`, never
    the human prose — so a re-ground finding whose prose mentions ``merge`` /
    ``plan-tool merge`` still classifies as ``reground`` (its marker's kind),
    never ``merge``. Returns ``None`` for any non-``granularity-merge`` source
    and for a finding carrying no well-formed marker.
    """
    if rec.source != _GRANULARITY_MERGE_SOURCE:
        return None
    if not rec.suggested_action:
        return None
    m = _MERGE_ACTION_MARKER_RE.search(rec.suggested_action)
    if m is None:
        return None
    step_ids = tuple(
        sorted(int(tok) for tok in m.group(2).replace(",", " ").split())
    )
    return MergeAction(kind=m.group(1), step_ids=step_ids)


def is_pairwise_merge_finding(rec: Recommendation) -> bool:
    """True for a per-pair ``granularity-merge`` finding (``step_id`` set) —
    whether it carries a dispatchable ``merge`` directive (contiguous pair) or
    is the gapped recommend-only advisory (no marker, non-dispatchable). Both
    are pairwise merge *advice* the operator should see; only the plan-wide
    re-ground directive (``step_id is None``) is not a merge. Keys on source +
    ``step_id`` rather than the machine marker so a gapped pair (which carries
    no marker) is not misclassified — the walk's ``skip_info`` carve uses this
    to keep gapped merge findings visible without ``--include-info``.
    """
    return rec.source == _GRANULARITY_MERGE_SOURCE and rec.step_id is not None


# Detail-quality conceptual-altitude advisories: the detail prose reads too
# mechanically prescriptive, but the right fix needs human judgment. Keep this
# source absent from APPLY_ELIGIBLE_SOURCES and STRUCTURAL_SOURCES so it is
# reported but never dispatched to apply_finding, even when include_info=True.
DETAIL_ALTITUDE_SOURCE = "detail-altitude"


def is_structural(rec: Recommendation) -> bool:
    """True when ``rec``'s only correct fix is to split its step into two
    (see :data:`STRUCTURAL_SOURCES`). These route to the split bridge, not
    ``apply_finding``; :func:`triage_reason` gives them a split-specific
    message pointing at ``plan-tool split``."""
    return rec.source in STRUCTURAL_SOURCES


# Sources whose ``suggested_action`` is a ``→ fix:`` targeted
# *plan/detail edit* (the concrete thing apply will do), not a follow-up
# command or check. Only these may be rendered under the "will apply"
# label and injected into the apply prompt's ``## Targeted fix`` section.
# The plan-audit axes (``plan-completeness`` / ``plan-correctness``),
# ``detail-reconcile``, and the reconcile-plan semantic pass (``claude``)
# qualify — each is applied via ``apply_finding``, which makes exactly the
# plan/detail edit the fix names. ``run-reconcile`` is deliberately
# EXCLUDED: it carries a ``→ fix:`` too, but its code edits already landed
# inline during the audit (no per-finding apply), so its fix is
# informational and stays under the neutral "suggested" label. Other
# apply-eligible sources (``detail-body``, ``body-completeness``) carry a
# shell command or a "fill in this section" hint on ``suggested_action`` —
# injecting that as "apply exactly this" would misdirect claude, so
# :func:`audit_targeted_fix` gates them out.
AUDIT_FIX_SOURCES: frozenset[str] = frozenset(
    {"plan-completeness", "plan-correctness", "detail-reconcile", "claude"}
)


def audit_targeted_fix(rec: Recommendation) -> Optional[str]:
    """The audit's targeted-fix edit for ``rec``, or ``None``.

    Returns ``rec.suggested_action`` only for the sources in
    :data:`AUDIT_FIX_SOURCES` (the plan-audit axes, ``detail-reconcile``,
    and the reconcile-plan ``claude`` pass), whose action IS the
    plan/detail edit apply will make. ``None`` for every other source so a
    follow-up command/check — or a ``run-reconcile`` fix whose code edit
    already landed inline — is never fed to :func:`apply_finding` as the
    edit to apply verbatim.
    """
    return rec.suggested_action if rec.source in AUDIT_FIX_SOURCES else None


def should_apply_by_triage(rec: Recommendation) -> bool:
    """Return ``True`` when the iteration loop should spend tokens
    applying ``rec``, ``False`` when it should skip + report.

    Triage rule (session 4 follow-up):

    - Skip when ``rec.complexity`` strictly exceeds ``rec.impact``
      (low+medium, low+high, medium+high).
    - Apply in all other cases:
      - impact >= complexity (high+anything, medium+low/medium,
        low+low).
      - Either tag missing/unrecognized (no triage signal → default
        to apply).

    The "complexity > impact" rule captures the user's intent from
    the design conversation: "low priority + hard = skip; medium +
    high complexity = skip". Findings whose payoff doesn't justify
    the apply-cost are deferred; the surrounding iteration loop
    records them in a separate bucket so the convergence check
    doesn't keep re-evaluating them each round.

    Findings that lack triage tags surface as ``apply`` so the
    legacy behavior (apply every finding) is preserved when the
    reconcile prompt's Impact/Complexity emit is missing or
    malformed. Operators who want to override this default can pass
    ``--no-triage`` at the CLI surface.
    """
    impact = _triage_level(rec.impact)
    complexity = _triage_level(rec.complexity)
    if impact < 0 or complexity < 0:
        # No usable triage signal — apply (legacy default).
        return True
    return complexity <= impact


def triage_reason(rec: Recommendation) -> str:
    """Short human-readable reason for skipping ``rec``. Suitable
    for stderr summaries / rollup rendering. Assumes the caller
    already decided to defer ``rec`` (structural-diagnostic source,
    info-severity exclusion, or ``should_apply_by_triage(rec) is
    False``)."""
    if is_structural(rec):
        if rec.source == "structural-split":
            return (
                "structural-split: the only correct fix is to split this "
                "step into two type-pure steps; run `plan-tool split`, not "
                "an apply edit"
            )
        return (
            "granularity-split: structural — step is over-packed / mixes "
            "concerns; the fix is to split it into type-pure steps via "
            "`plan-tool split`, not an apply edit"
        )
    if rec.source == _GRANULARITY_MERGE_SOURCE:
        # Shared by granularity.py's plan-structure merge detectors and
        # reconcile's code-grounded re-ground finding — wording must stay
        # producer-neutral (no unconditional "code already implements this").
        return (
            "granularity-merge: merge/re-ground advisory — inspect the "
            "finding; merge a contiguous all-PENDING run or re-baseline / "
            "mark done / re-decompose an already-built set"
        )
    if rec.source == DETAIL_ALTITUDE_SOURCE:
        return (
            "detail-altitude: advisory detail-quality altitude issue — "
            "inspect manually; demote over-prescriptive mechanics to "
            "examples/notes, not an automatic apply edit"
        )
    if rec.source == INTENT_PRESENCE_SOURCE:
        # The generic branch below would send an operator off to fix a path or
        # author lessons; the actual remedy is one frontmatter line.
        return (
            "intent-presence: blocks completeness convergence — add a one-line "
            "`intent:` to the plan or to the named step(s); a frontmatter "
            "field is not an apply edit"
        )
    if not is_apply_eligible(rec):
        return (
            f"{rec.source}: structural diagnostic — not auto-fixable by "
            f"an apply pass; resolve directly (fix the path / run "
            f"`plan-tool detail` / author lessons)"
        )
    if rec.severity.lower() == "info":
        return "info severity (advisory; pass --include-info to apply)"
    impact = rec.impact or "?"
    complexity = rec.complexity or "?"
    return (
        f"complexity={complexity} > impact={impact} (deferred by "
        f"triage)"
    )


def partition_findings_for_triage(
    findings: list[Recommendation],
    *,
    triage_enabled: bool = True,
    include_info: bool = False,
    apply_eligible_only: bool = True,
) -> "tuple[list[Recommendation], list[Recommendation]]":
    """Split ``findings`` into ``(open_apply, open_deferred)``.

    Three gates, applied in this order:

    1. **Apply-eligibility** (default ON, ``apply_eligible_only``).
       Structural-diagnostic findings (a path that doesn't resolve, a
       dep-graph gap, a missing detail file, ...) are deferred because
       :func:`apply_finding` -- a plan/detail prose editor -- can't fix
       them; dispatching them only burns a claude call that returns
       NOT-APPLICABLE. See :func:`is_apply_eligible`. This gate is
       independent of ``triage_enabled``: ``--no-triage`` force-applies
       eligible findings but still won't dispatch a diagnostic that has
       no apply remedy.
    2. **Info-severity exclusion** (default ON). ``info`` findings are
       advisory observations -- low payoff for an apply pass, deferred
       by default. Pass ``include_info=True`` (CLI ``--include-info``)
       to apply them. Runs regardless of ``triage_enabled``.
    3. **Complexity-vs-impact triage** (``triage_enabled``, the CLI
       ``--no-triage`` opt-out). When True, findings whose complexity
       strictly exceeds their impact are deferred. Findings without
       triage tags fail open to ``open_apply`` --
       :func:`should_apply_by_triage` treats missing tags as "no signal,
       apply by default".

    Deferred findings are reported (not silently dropped) by
    :func:`emit_triage_summary`; :func:`triage_reason` distinguishes the
    three deferral reasons.
    """
    open_apply: list[Recommendation] = []
    open_deferred: list[Recommendation] = []
    for rec in findings:
        if apply_eligible_only and not is_apply_eligible(rec):
            open_deferred.append(rec)
            continue
        if not include_info and rec.severity.lower() == "info":
            open_deferred.append(rec)
            continue
        if not triage_enabled:
            open_apply.append(rec)
            continue
        if should_apply_by_triage(rec):
            open_apply.append(rec)
        else:
            open_deferred.append(rec)
    return open_apply, open_deferred


def emit_triage_summary(
    deferred: list[Recommendation],
    *,
    iteration_label: str,
    file=None,
) -> None:
    """Print a structured stderr summary of triage-deferred findings.

    Used by each iteration entry point on every iteration that has
    deferred findings. Empty ``deferred`` is a no-op so callers can
    pass the partition result unconditionally.

    ``iteration_label`` is a free-form caller-supplied tag (e.g.
    ``"iteration 2"`` or ``"step 3"``) that surfaces in the
    summary header so operators reviewing multiple sessions can
    correlate stderr lines to source iteration.
    """
    if not deferred:
        return
    import sys

    out = file if file is not None else sys.stderr
    tool(
        f"deferring {len(deferred)} finding(s) by triage "
        f"({iteration_label}). Apply manually if the complexity is "
        f"worth the impact -- the iteration loop will short-circuit "
        f"if these are the only findings remaining:",
        stream=out,
    )
    for rec in deferred:
        print(
            f"  - {rec.id}: {rec.title} [{triage_reason(rec)}] "
            f"[{confidence_label(rec.confidence)}]",
            file=out,
        )
        # Structural-split recs carry a split rationale (``body``) and a
        # concrete ``plan-tool split`` invocation (``suggested_action``);
        # render both as indented children of the bullet so the operator
        # sees why and how to split. Gated on ``is_structural`` so every
        # non-structural rec keeps its single-line form (preserves the
        # byte-identical summary guard).
        if is_structural(rec):
            print(f"      {rec.body}", file=out)
            if rec.suggested_action is not None:
                print(f"      {rec.suggested_action}", file=out)


def _claude_recommendations(stdout: str) -> list[Recommendation]:
    # Imported lazily to avoid the launcher → review import cycle on
    # module load. ``parse_finding_bullets`` is the bullet-level
    # companion to ``summarize_findings``.
    from plan_tool.launcher import parse_finding_bullets

    bullets = parse_finding_bullets(stdout)
    out: list[Recommendation] = []
    for bullet in bullets:
        raw_sev, body = _recover_severity_from_body(
            bullet.severity, bullet.body
        )
        sev = _CLAUDE_SEVERITY_MAP.get(raw_sev, "info")
        # Strip an optional trailing triage tag (so the marker runs to
        # end-of-body), then split the ``→ fix:`` remediation onto
        # suggested_action so the walk renders it as "will apply" and the
        # apply injects it as the targeted edit. Body/title/id derive from
        # the fix-stripped prose so a reworded fix can't destabilize the id
        # — mirrors the plan-audit / reconcile parsers.
        impact, complexity, body = _split_triage_tags(body)
        fix, body = _split_audit_fix(body)
        sev, _coerced = _enforce_high_impact_severity(
            sev,
            impact,
            severity_established=raw_sev != "UNSPECIFIED",
        )
        title = body.splitlines()[0][:120] if body else "(unspecified)"
        out.append(
            Recommendation(
                id=_make_rec_id(None, "claude", body),
                source="claude",
                severity=sev,
                step_id=None,
                title=title,
                body=body,
                suggested_action=fix,
                impact=impact,
                complexity=complexity,
            )
        )
    return out


@dataclass(frozen=True)
class ReviewResult:
    """Full output of one ``review_plan_full`` invocation.

    Returned in addition to the markdown ``report`` so callers (e.g. the
    save-by-default CLI path) can persist the structured
    ``recommendations`` without re-parsing the report. ``dry_run`` is
    True when the result carries a rendered prompt rather than a real
    review — same shape, but the recommendations list is empty and
    ``report`` is the prompt.
    """

    report: str
    recommendations: list[Recommendation]
    dry_run: bool = False


def collect_deterministic_findings(
    plan: Plan,
    plan_path: Path,
    *,
    repo_root: Path,
    plan_name: str,
    step_filter: Optional[int] = None,
) -> list[Recommendation]:
    """Run every deterministic primitive and return a flat
    ``Recommendation`` list with stable IDs.

    Used by ``apply_finding`` to compute pre/post deltas around a
    plan edit. Excludes the heuristic ("looks already done") scan
    because it's informational, not a regression a plan edit can
    introduce or resolve. Excludes Claude's semantic findings for
    the same reason — and also because we run this synchronously,
    no subprocess calls allowed.

    Stable rec IDs (via :func:`_make_rec_id`) make pre/post set
    comparison trivial — matching IDs in both sets mean the issue
    persisted; new IDs in post are regressions; missing IDs from pre
    are resolutions.

    Called directly by ``apply_finding`` and its findings-delta helper
    (unlike the completeness-audit CLI path, which reaches
    ``check_body_completeness`` only after its own upstream fence guard) —
    guard here too so an unmatched opening fence can't corrupt
    ``check_body_completeness``'s section split into spurious missing-section
    findings on those paths.
    """
    _reject_unmatched_plan_fence(plan_path)
    file_checks = check_file_existence(plan, repo_root)
    path_style_hint = detect_path_style_mismatch(file_checks, repo_root)
    dep_issues = validate_deps(plan)
    body_issues = check_body_completeness(plan_path)
    detail_cov_issues = check_detail_coverage(plan, plan_path, repo_root)
    detail_body_issues = check_detail_body_completeness(
        plan, repo_root, plan_path=plan_path
    )
    files_coh_issues = check_files_coherence(plan, repo_root, plan_path=plan_path)
    lessons_issues = check_lessons_coverage(plan, repo_root)
    input_contract_issues = check_input_contract_references(
        plan, plan_path, repo_root, step_filter=step_filter
    )

    recs = extract_recommendations(
        plan,
        plan_name,
        repo_root=repo_root,
        file_checks=file_checks,
        heuristic_hits=[],
        dep_issues=dep_issues,
        path_style_hint=path_style_hint,
        claude_stdout=None,
        step_filter=step_filter,
        body_completeness=body_issues,
        detail_coverage=detail_cov_issues,
        detail_body=detail_body_issues,
        files_coherence=files_coh_issues,
        lessons_coverage=lessons_issues,
        input_contract_references=input_contract_issues,
    )
    # Append the per-step ``change_type`` alignment audit *after*
    # ``extract_recommendations`` — never as a parameter to it — so these
    # ``source="test-strategy"`` findings reach only the completeness flow
    # and never the standalone ``review`` report. The check scans the whole
    # plan regardless of ``step_filter``, like the other plan-wide checks.
    recs.extend(
        check_test_strategy_alignment(plan)
    )
    return recs


# --- Criteria fulfillment (Fulfillment axis: code ⊇ plan) -----------------

# Layered ON TOP of ``collect_deterministic_findings``: the deterministic
# primitives confirm the plan ARTIFACT is in good shape (sections filled,
# files exist, deps coherent); this function asks whether the actual code
# delivers on the plan's stated ACCEPTANCE CRITERIA. Procedural
# completeness ≠ criteria fulfillment — a plan can ship every checklist
# item without solving the problem it was authored to solve (Lesson 1).
#
# This is the *Fulfillment* axis (does the code fulfill the plan), distinct
# from the *conceptual* audit in :func:`check_plan_audit` below (are the
# plan's own concepts correct, complete, and unambiguous, grounded in the
# per-step detail bundle and the code at HEAD).


def _extract_acceptance_criteria(plan_path: Path) -> Optional[str]:
    """Return the body of the plan's ``## Acceptance criteria`` H2
    section, or ``None`` when missing / empty / placeholder.

    Mirrors :func:`split_body_sections`'s key shape: heading text
    lowercased, trailing punctuation trimmed. The H2 name match is
    tolerant of common variants (``Acceptance criteria``,
    ``Acceptance``).
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return None
    split = _split_frontmatter(text)
    sections = split_body_sections(split.body, ignore_fenced_code=True)
    body = sections.get("acceptance criteria") or sections.get("acceptance")
    if body is None:
        return None
    if _body_section_is_empty(body) or _body_section_is_placeholder(body):
        return None
    return body


def _collect_done_step_file_contents(
    plan: Plan,
    repo_root: Path,
    *,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
) -> str:
    """Render the contents of every DONE step's ``step.files`` as a
    markdown block. Empty string when no DONE step declares files.

    Mirrors the file-contents block in ``render_review_prompt`` so the
    excerpt / unreadable / not-on-disk wording stays consistent.
    """
    path_order: list[str] = []
    path_candidates: dict[str, list[str]] = {}
    path_step_ids: dict[str, int] = {}
    for step in plan.steps:
        if step.status != StepStatus.DONE:
            continue
        step_candidates = _derive_symbols(step.title)
        for f in step.files:
            if f not in path_candidates:
                path_candidates[f] = []
                path_step_ids[f] = step.id
                path_order.append(f)
            _merge_candidate_symbols(path_candidates[f], step_candidates)
            _merge_candidate_symbols(
                path_candidates[f], _derive_file_path_symbols(f)
            )

    blocks: list[str] = []
    for f in path_order:
        path = repo_root / f
        if not path.is_file():
            blocks.append(f"### `{f}` _(not on disk)_\n")
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            blocks.append(f"### `{f}` _(unreadable: {exc})_\n")
            continue
        excerpt = build_prompt_excerpt(
            f,
            body,
            path_candidates[f],
            max_bytes=max_file_bytes,
        )
        blocks.append(
            f"### `{f}` (from step {path_step_ids[f]})\n\n"
            f"```\n{excerpt.text}\n```\n"
        )
    return "\n".join(blocks)


def render_criteria_fulfillment_prompt(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    *,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
) -> Optional[str]:
    """Render ``prompts/criteria-fulfillment.md`` for this plan.

    Returns ``None`` (and the caller skips the claude call) when the
    plan has no actionable acceptance criteria OR no DONE step declares
    files. Both conditions mean criteria fulfillment is
    unanswerable: there's either no spec to check against, or nothing
    built yet to evaluate.
    """
    acceptance = _extract_acceptance_criteria(plan_path)
    if acceptance is None:
        return None
    done_files = _collect_done_step_file_contents(
        plan, repo_root, max_file_bytes=max_file_bytes
    )
    if not done_files.strip():
        return None
    template_path = prompts_dir() / "criteria-fulfillment.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.safe_substitute(
        plan_title=plan.title,
        acceptance_criteria_block=acceptance,
        done_files_block=done_files,
        findings_response_format_block=FINDINGS_RESPONSE_CONTRACT.render_prompt_block(),
    )


def _attribute_concept_finding_step(
    body: str, file_to_step: dict[str, int]
) -> Optional[int]:
    """Heuristically infer which step a concept finding belongs to.

    Scans ``body`` for mentions of any file path that maps to a step
    via ``file_to_step`` (built from DONE steps' ``step.files``).
    Returns the matched step id when exactly one step's files appear,
    else ``None`` — ambiguous matches fall back to apply_finding's
    default routing so we don't over-claim attribution. Backticked
    paths (`foo/bar.py`) are checked first as the stronger signal;
    bare path matches are a secondary fallback.

    Without this attribution, apply_finding routes step_id=None
    findings to the "current/next runnable" step, which is unrelated
    to the file the criterion gap actually lives in -- causing
    scope-guard to revert legitimate code edits.
    """
    if not file_to_step:
        return None

    matched_steps: set[int] = set()
    for path, step_id in file_to_step.items():
        # Backticked form is the conventional anchor; check it first.
        if f"`{path}`" in body:
            matched_steps.add(step_id)
            continue
        # Fallback: bare word-boundary match. Avoid substring matches
        # like "foo" hitting both "foo.py" and "foobar.py" by anchoring
        # against non-word characters (or start/end of string).
        pattern = r"(?:^|[^\w/.\-])" + re.escape(path) + r"(?:$|[^\w/.\-])"
        if re.search(pattern, body):
            matched_steps.add(step_id)

    if len(matched_steps) == 1:
        return matched_steps.pop()
    return None


def check_criteria_fulfillment(
    plan: Plan,
    plan_path: Path,
    *,
    repo_root: Path,
    invoker: Optional[Invoker] = None,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
    log_file=None,
) -> list[Recommendation]:
    """Audit whether the plan's acceptance criteria are fulfilled by
    the current code state of DONE steps (Fulfillment axis: code ⊇ plan).

    Semantic check — invokes ``invoker`` with the rendered
    ``criteria-fulfillment`` prompt and parses claude's
    ``## Findings`` block. Findings come back as
    :class:`Recommendation` with ``source="criteria-fulfillment"`` so
    the downstream apply pipeline routes them through the same
    intent-preserving gate as deterministic findings.

    Returns ``[]`` (no claude call attempted) when:

    - ``invoker`` is ``None`` (offline / no semantic check available)
    - The plan has no ``## Acceptance criteria`` body, or its body is
      a placeholder / empty
    - No DONE step declares any files (nothing built yet to check)
    - The invoker raises or returns a non-zero exit code

    The check is per-plan, not per-step: a single claude call audits
    all acceptance criteria against all DONE-step file contents,
    matching the user's "always run, single semantic pass" design.

    A one-line ``plan-tool: criteria-fulfillment: ...`` summary is
    written to ``log_file`` (default ``sys.stderr``) at the end of
    every call so operators in CI environments can tell whether the
    check actually ran. Pass ``log_file=os.devnull`` (or any writable
    sink) to suppress the line in noise-sensitive contexts.
    """
    out = log_file if log_file is not None else sys.stderr

    def _log_skip(reason: str) -> None:
        tool(f"criteria-fulfillment: skipped ({reason})", stream=out)

    if invoker is None:
        _log_skip("no invoker configured")
        return []
    prompt = render_criteria_fulfillment_prompt(
        plan, plan_path, repo_root, max_file_bytes=max_file_bytes
    )
    if prompt is None:
        # Distinguish the two skip reasons so operators know which gap
        # to address (add acceptance criteria, or mark a step DONE).
        if _extract_acceptance_criteria(plan_path) is None:
            _log_skip(
                "no actionable `## Acceptance criteria` section in "
                "plan body"
            )
        else:
            _log_skip("no DONE step declares files to audit against")
        return []
    try:
        exit_code, stdout = invoker(prompt)
    except Exception as exc:  # noqa: BLE001 — claude shell-out can fail for many reasons
        _log_skip(f"invoker raised: {exc!r}")
        return []
    if exit_code != 0:
        _log_skip(
            f"invoker exited non-zero (code {exit_code}); "
            f"claude may not be on PATH"
        )
        return []
    recs = _claude_recommendations(stdout)

    # Build a file→step map from DONE steps so we can attribute each
    # finding to the step whose ``step.files`` mentions the cited path.
    # First-mention wins on duplicates so we don't lose attribution for
    # files declared by multiple steps (unusual but valid).
    file_to_step: dict[str, int] = {}
    for step in plan.steps:
        if step.status != StepStatus.DONE:
            continue
        for f in step.files:
            if f not in file_to_step:
                file_to_step[f] = step.id

    # Override the bare-claude source so downstream routing
    # (rollup labels, apply-finding scope decisions) can distinguish
    # criteria-fulfillment findings from generic claude review output.
    # Attribute step_id heuristically so apply_finding routes to the
    # step whose files actually hold the criterion gap, rather than
    # falling back to "current/next runnable" (which scope-guard would
    # then revert as out-of-scope).
    attributed = [
        Recommendation(
            id=r.id,
            source="criteria-fulfillment",
            severity=r.severity,
            step_id=_attribute_concept_finding_step(r.body, file_to_step),
            title=r.title,
            body=r.body,
            suggested_action=r.suggested_action,
        )
        for r in recs
    ]

    # Success summary -- mirrors the skip lines above so every call
    # produces exactly one structured stderr line describing what
    # happened. Operators in CI can grep these to confirm the check
    # ran AND to spot zero-finding clean runs vs noisy ones.
    if attributed:
        tool(
            f"criteria-fulfillment: {len(attributed)} finding(s) raised",
            stream=out,
        )
    else:
        tool(
            "criteria-fulfillment: 0 findings "
            "(plan's acceptance criteria appear met by the code)",
            stream=out,
        )
    return attributed


# --- Conceptual audit (Conceptual axis: plan ⊨ its own problem) -----------
#
# Plan-only semantic pass: reads the plan body with NO code in context and
# judges the plan's own concepts on two persisted axes — *correctness* (are the
# stated ideas sound, internally consistent, and free of material ambiguity)
# and *completeness* (does the plan cover everything its problem statement
# implies). This mirrors what the convergence loop audits (correctness +
# completeness together), and is distinct from both the deterministic
# well-formedness primitives and the code-aware
# :func:`check_criteria_fulfillment`. Always runnable —
# unlike fulfillment, it does not gate on DONE steps, since a freshly
# authored plan is exactly when conceptual gaps matter most.


def _collect_plan_body(plan_path: Path) -> Optional[str]:
    """Return the plan's frontmatter-stripped markdown body.

    ``None`` when the file is unreadable or has no body to audit.
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return None
    body = _split_frontmatter(text).body.strip()
    return body or None


# The ordered machine-response contract drives the prompt, parser, and retry.
# ``key`` is the source that places parsed findings in the report's layer.
_PLAN_AUDIT_RESPONSE_CONTRACT = MarkdownSectionsContract(
    sections=(
        ResponseSection("Correctness findings", "plan-correctness"),
        ResponseSection("Completeness findings", "plan-completeness"),
    )
)
_PLAN_AUDIT_SECTION_RE = _PLAN_AUDIT_RESPONSE_CONTRACT.heading_pattern()


def _findings_under_heading(stdout: str, heading: str) -> list:
    """Extract severity bullets under one ``## <heading>`` H2 section.

    Slices the section body (from the heading to the next H2 or EOF),
    re-labels it as a ``## Findings`` block, and reuses
    :func:`parse_finding_bullets` so the battle-tested bullet/severity/
    ``_(none)_`` handling stays in one place. Returns the parser's
    ``FindingBullet`` list (empty when the section is absent or empty).
    """
    from plan_tool.launcher import _ANSI_RE, parse_finding_bullets

    clean = _ANSI_RE.sub("", stdout)
    target = heading.lower()
    matches = list(_PLAN_AUDIT_SECTION_RE.finditer(clean))
    for i, m in enumerate(matches):
        if m.group(1).lower() != target:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
        section = clean[start:end]
        return parse_finding_bullets("## Findings\n" + section)
    return []


# Leading ``[anchor-slug]`` the plan-audit prompt prepends to each
# finding bullet. The slug names the *concept* a finding is about
# (a section, step id, criterion, or risk) rather than the prose, so it
# stays stable when a re-audit re-phrases the same gap -- which is what
# lets ``_make_rec_id`` mint a stable id across runs instead of a fresh
# content hash every time. The slug itself is kebab-case alphanumerics.
# ``**``/``` ` ``` wrappers are tolerated so ``**[slug]**`` and
# ``` `[slug]` ``` land on the same anchor as the bare form -- otherwise
# the finding re-hashes every run and recurrence detection degrades to
# fuzzy title matching. The trailing wrapper is stripped only when it
# *mirrors* the leading one (see :func:`_split_audit_key`); a bare
# ``[slug]`` followed by prose that merely starts with a marker keeps
# that marker. ``(?!\()`` stops a leading markdown link from being read
# as an anchor.
_PLAN_AUDIT_KEY_RE = re.compile(
    r"^\s*(?P<open>(?:\*\*|`)*)"
    r"\[(?P<slug>[a-z0-9][a-z0-9-]*)\](?!\()"
    r"(?P<rest>.*)\Z",
    re.DOTALL,
)


def _mirror_wrapper(opened: str) -> str:
    """The closing form of a ``**``/``` ` ``` wrapper stack: same tokens,
    reversed (``**` `` closes with ``` `** ```)."""
    return "".join(reversed(re.findall(r"\*\*|`", opened)))


def _split_audit_key(body: str) -> tuple[Optional[str], str]:
    """Split a leading ``[anchor-slug]`` off a plan-audit finding body.

    Returns ``(slug, remaining_body)`` when the bullet opens with a
    bracketed kebab slug (the prompt's stable-key contract), else
    ``(None, body)`` unchanged. The slug is stripped from the returned
    body so it doesn't leak into the rendered title/report.

    A trailing wrapper is consumed only when it mirrors the leading one,
    so ``[slug]`code` …`` keeps the backtick that opens its prose.
    """
    m = _PLAN_AUDIT_KEY_RE.match(body)
    if not m:
        return None, body
    rest = m.group("rest")
    closer = _mirror_wrapper(m.group("open"))
    if closer and rest.startswith(closer):
        rest = rest[len(closer):]
    return m.group("slug"), rest.lstrip()


# The audit-shape tag is deliberately a separate, literal slot after the
# stable anchor. It is audit evidence, not Recommendation routing metadata.
_AUDIT_STEP_TOKEN_RE = re.compile(r"\[audit-step:(?P<value>[^\]]*)\]")
_AUDIT_STEP_VALUE_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")


def _split_audit_step_evidence(
    body: str,
    *,
    valid_target_ids: frozenset[int],
) -> tuple[Optional[int], str]:
    """Extract a single valid literal audit-step slot and remove all tags.

    A malformed, repeated, unknown, or prose-positioned token intentionally
    yields no target. Tokens are stripped regardless, keeping ephemeral audit
    evidence out of recommendation title/body/fingerprints.
    """
    tokens = list(_AUDIT_STEP_TOKEN_RE.finditer(body))
    cleaned = _AUDIT_STEP_TOKEN_RE.sub("", body)
    key_match = _PLAN_AUDIT_KEY_RE.match(body)
    if len(tokens) != 1 or key_match is None:
        return None, cleaned
    token = tokens[0]
    rest_start = key_match.start("rest")
    # The literal slot is one horizontal whitespace separator after the anchor;
    # no wrapper, prose, newline, or adjacent bracket form is attribution.
    if re.fullmatch(r"[ \t]+", body[rest_start:token.start()]) is None:
        return None, cleaned
    raw_value = token.group("value")
    if _AUDIT_STEP_VALUE_RE.fullmatch(raw_value) is None:
        return None, cleaned
    target = int(raw_value)
    if target not in valid_target_ids:
        return None, cleaned
    return target, cleaned


# Inline ``(impact=<level>, complexity=<level>)`` triage tag emitted by
# both the plan-audit prompt (trailing on each finding) and the
# reconcile prompts (inline on each bullet's first line). The two values
# are pulled independently (order-tolerant; ``:`` or ``=`` separator),
# then the parenthetical that carries them is stripped so it doesn't
# leak into the rendered body/title. The strip is NOT end-anchored, so
# it also catches the reconcile case where the pair sits on the first
# line ahead of a multi-line ``## Redirect`` sub-block. The lookahead
# requires ``impact``/``complexity`` *inside* the parens, so a prose
# aside like ``(see step 2)`` is left untouched. ``_triage_level`` maps
# the lowercased value -> ordinal for the triage gate.
_TRIAGE_IMPACT_RE = re.compile(
    r"impact\s*[:=]\s*(low|medium|high)", re.IGNORECASE
)
_TRIAGE_COMPLEXITY_RE = re.compile(
    r"complexity\s*[:=]\s*(low|medium|high)", re.IGNORECASE
)
_TRIAGE_PAREN_RE = re.compile(
    r"\s*\((?=[^)]*(?:impact|complexity)\s*[:=])[^)]*\)",
    re.IGNORECASE,
)


def _split_triage_tags(
    body: str,
) -> tuple[Optional[str], Optional[str], str]:
    """Pull the ``(impact=…, complexity=…)`` triage tag off a finding.

    Returns ``(impact, complexity, remaining_body)`` with the levels
    lowercased (or ``None`` when absent) and the triage parenthetical
    stripped from the body. Shared by :func:`check_plan_audit` and
    :func:`extract_reconcile_recommendations`. Missing/partial tags
    degrade gracefully: a finding with no tag yields ``(None, None,
    body)`` and falls open to "apply" in :func:`should_apply_by_triage`.
    """
    mi = _TRIAGE_IMPACT_RE.search(body)
    mc = _TRIAGE_COMPLEXITY_RE.search(body)
    impact = mi.group(1).lower() if mi else None
    complexity = mc.group(1).lower() if mc else None
    cleaned = _TRIAGE_PAREN_RE.sub("", body).rstrip()
    return impact, complexity, cleaned


# Fenced citations cannot supply live annotation boundaries.


def _outside_fences(
    matches: list[re.Match[str]], spans: list[tuple[int, int]]
) -> list[re.Match[str]]:
    return [
        m for m in matches if not any(s <= m.start() < e for s, e in spans)
    ]


def _excise_fenced(text: str, start: int, end: int, spans: list[tuple[int, int]]) -> str:
    """``text[start:end]`` with any fenced-span content removed.

    A fenced citation excluded from the boundary search (above) is still
    literal text sitting within a captured value's range -- between two
    real headings, or trailing a real marker; without this, the value
    would swallow the whole fenced span verbatim, backticks and embedded
    fake structure included.
    """
    pieces = []
    cursor = start
    for s, e in spans:
        if e <= cursor or s >= end:
            continue
        seg_start = max(s, cursor)
        if seg_start > cursor:
            pieces.append(text[cursor:seg_start])
        cursor = max(cursor, min(e, end))
    pieces.append(text[cursor:end])
    return "".join(pieces)


# Reconcile-family prompts (detail-reconcile/run-reconcile) inline this
# marker via plan-audit's original convention; plan-audit itself moved to
# :func:`_split_audit_restated_and_fix`. Split before the id fingerprint is
# computed so wording can't destabilize it.
_PLAN_AUDIT_FIX_MARKER_RE = re.compile(
    r"\s*(?:→|->)\s*fix\s*[:=]\s*", re.IGNORECASE
)


def _split_audit_fix(body: str) -> tuple[Optional[str], str]:
    """Split a trailing ``→ fix: …`` off a reconcile-family finding body.

    Returns ``(fix, gap_body)`` when the bullet carries the marker (the
    prompt's targeted-fix contract), else ``(None, body)`` unchanged.
    Whitespace in the captured fix is collapsed so a wrapped two-line
    fix renders as one line. Uses the LAST non-fenced occurrence -- the
    marker is trailing by contract, so an earlier fix-shaped occurrence
    (fenced citation or otherwise) must not win -- and excises any fenced
    span from the captured value too, in case the citation trails the
    marker rather than precedes it. Call AFTER :func:`_split_triage_tags`
    so the trailing triage parenthetical is already gone and the marker
    runs to end-of-body.
    """
    spans = fenced_spans(body)
    matches = _outside_fences(
        list(_PLAN_AUDIT_FIX_MARKER_RE.finditer(body)), spans
    )
    if not matches:
        return None, body
    m = matches[-1]
    fix = " ".join(_excise_fenced(body, m.end(), len(body), spans).split())
    return (fix or None), body[: m.start()].rstrip()


# ``### Restated`` / ``### Fix`` sub-blocks, mirroring ``## Redirect``'s own
# heading-anchored convention (parse_redirect_block). See CLAUDE.md's
# "heading-anchored sub-blocks" for why this needs the fence exclusion too.
_PLAN_AUDIT_SUBBLOCK_HEADING_RE = re.compile(
    r"^[ \t]*###\s*(Restated|Fix)\b:?[ \t]*\n?", re.MULTILINE | re.IGNORECASE
)


def _split_audit_restated_and_fix(
    body: str,
) -> tuple[Optional[str], Optional[str], str]:
    """Split ``### Restated`` / ``### Fix`` sub-blocks off a plan-audit
    finding body, in whichever order the model emitted them.

    Returns ``(restated, fix, gap_body)`` — either value ``None`` when its
    sub-block is absent. A repeated heading of the same kind keeps its
    first NON-EMPTY occurrence (an empty stray heading doesn't shadow real
    content that follows it). Call BEFORE :func:`_split_triage_tags`: the
    sub-blocks trail the whole bullet, triage tag included, not just the
    gap prose.
    """
    spans = fenced_spans(body)
    matches = _outside_fences(
        list(_PLAN_AUDIT_SUBBLOCK_HEADING_RE.finditer(body)), spans
    )
    if not matches:
        return None, None, body.rstrip()
    values: dict[str, Optional[str]] = {"fix": None, "restated": None}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        # A fenced span can sit between two real headings (e.g. a
        # duplicate-heading citation), so excise fenced text -- not just
        # exclude fenced heading matches -- before capturing the value.
        value = " ".join(_excise_fenced(body, start, end, spans).split())
        # A colon after the heading word (``### Fix:``, ``### Fix :``,
        # even doubled) isn't consumed by the heading regex in every
        # spacing variant; strip it here instead of chasing each variant
        # in the regex.
        value = value.lstrip(":").lstrip()
        key = m.group(1).lower()
        if value and values[key] is None:
            values[key] = value
    gap_body = body[: matches[0].start()].rstrip()
    return values["restated"], values["fix"], gap_body


# When the bullet header doesn't match ``- SEVERITY:`` (common misshape:
# ``- HIGH `[anchor]`: prose``), ``parse_finding_bullets`` parks the whole
# line as UNSPECIFIED and the real severity + slug sit at the head of
# ``body``. Lift them so severity/anchor don't silently default to
# ``info``/None while ``impact=high`` still extracts from the triage tag.
# Require a real header cue after the token — ``:``, a dash *separator*
# (``-`` + whitespace, not a hyphenated word), or an opening ``[anchor]``
# (optionally wrapped) — so English like "HIGH priority…" / "high-level…"
# is not promoted.
_BODY_LEADING_SEV_RE = re.compile(
    r"^\s*(?:\*\*)?(?P<sev>CRITICAL|HIGH|MEDIUM|NIT|LOW)(?:\*\*)?\s*"
    r"(?:"
    r":\s*"
    r"|"
    r"-\s+"
    r"|"
    r"(?=(?:(?:\*\*|`)*)\[)"
    r")",
    re.IGNORECASE,
)


def _recover_severity_from_body(
    severity: str, body: str,
) -> tuple[str, str]:
    """When ``severity`` is UNSPECIFIED, lift a leading severity token off
    ``body``. Returns ``(severity, body)`` unchanged when already labelled or
    when no leading token is present."""
    if severity != "UNSPECIFIED":
        return severity, body
    m = _BODY_LEADING_SEV_RE.match(body)
    if not m:
        return severity, body
    return m.group("sev").upper(), body[m.end():].lstrip()


_ADVISORY_SEVERITIES = frozenset({"info", "nit"})

# An unlabelled finding maps to ``info``.  ``impact=high`` is sufficient to
# repair that missing severity, but it must never overwrite an explicit
# ``NIT:`` or ``INFO:`` label: severity and impact are separate fields and the
# explicit prefix is the producer's severity judgment.
_SEVERITIES_INCOHERENT_WITH_HIGH_IMPACT = frozenset({"info"})


def _enforce_high_impact_severity(
    severity: str,
    impact: Optional[str],
    *,
    severity_established: bool,
) -> tuple[str, bool]:
    """Backfill an omitted severity from a high-impact triage tag.

    Returns ``(severity, coerced)``. Call after body-leading recovery / rescue
    and pass ``severity_established=True`` for every explicit or recovered
    header label so a triage tag cannot replace it.
    """
    if (
        not severity_established
        and impact == "high"
        and severity in _SEVERITIES_INCOHERENT_WITH_HIGH_IMPACT
    ):
        return "high", True
    return severity, False


def _format_audit_detail_bundle(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    *,
    max_file_bytes: int,
    audit_input_snapshot=None,
) -> str:
    """Render each step's detail file under a ``### Step NN — <title>``
    header, capped at ``max_file_bytes``.

    The on-disk detail file resolves through
    :func:`plan_tool.detail_artifacts.resolve_detail_artifact` — the
    ``step.detail`` pointer (repo-relative) when set, the canonical path
    when unset — so a freshly-authored bundle still surfaces even
    before the plan's ``detail:`` pointers are written, and the body is a
    symbol-aware excerpt. Steps with no file on disk render a one-line note
    rather than a blank, so the audit can tell "no detail authored yet"
    from "detail says nothing about it."
    """
    out: list[str] = []
    for step in plan.steps:
        header = f"### Step {step.id:02d} — {step.title}"
        captured_detail = (
            audit_input_snapshot.detail_for_step(step.id)
            if audit_input_snapshot is not None
            else None
        )
        if captured_detail is not None:
            path = Path(captured_detail.selected_path)
            on_disk = captured_detail.state != "missing"
            rel_path = (
                step.detail
                if captured_detail.resolution == "pointer"
                else _repo_relative_posix(path, repo_root)
            )
        else:
            resolution = resolve_detail_artifact(plan_path, plan, step, repo_root)
            path = resolution.path
            on_disk = resolution.on_disk
            rel_path = (
                step.detail
                if resolution.pointer_set
                else _repo_relative_posix(path, repo_root)
            )
        if not on_disk:
            out.append(f"{header}\n\n_(no detail file on disk)_\n")
            continue
        if captured_detail is not None:
            if captured_detail.state == "unreadable":
                out.append(f"{header}\n\n_(unreadable)_\n")
                continue
            text = captured_detail.content.decode("utf-8", errors="replace")
        else:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                out.append(f"{header}\n\n_(unreadable: {exc})_\n")
                continue
        require_supported_detail_format_version(text, path=path)
        candidates = _derive_symbols(step.title)
        _merge_candidate_symbols(candidates, _derive_file_path_symbols(rel_path))
        excerpt = build_prompt_excerpt(
            rel_path,
            text,
            candidates,
            max_bytes=max_file_bytes,
        )
        out.append(f"{header}\n\n{excerpt.text}\n")
    if not out:
        return "_no steps to audit_"
    return "\n".join(out)


@dataclass(frozen=True)
class DetailBundleStatus:
    """Per-step detail-file presence at audit time (deterministic, no Claude).

    A plan is a **bare plan** when at least one step has no detail file on
    disk yet — the legitimate early-pipeline state of `create` → audit →
    `detail`. The completeness audit can run against it (the bundle renders
    a "no detail file" note per bare step), but it must do so *knowingly*:
    grounding is plan-level only for bare steps, so the audit must not raise
    detail-contradiction / detail-vs-code findings for them.
    """

    total: int
    detailed_step_ids: tuple[int, ...]
    bare_step_ids: tuple[int, ...]

    @property
    def detailed_count(self) -> int:
        return len(self.detailed_step_ids)

    @property
    def is_bare(self) -> bool:
        """True when at least one step has no detail file (partial or full)."""
        return bool(self.bare_step_ids)

    @property
    def is_fully_bare(self) -> bool:
        """True when no step has a detail file (a freshly-created plan)."""
        return self.total > 0 and self.detailed_count == 0


def audit_detail_bundle_status(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
    *,
    audit_input_snapshot=None,
) -> DetailBundleStatus:
    """Report detail presence using the same pointer/canonical resolution as the prompt.

    Captured inputs take precedence over disk so coverage describes the sampled bundle."""
    detailed: list[int] = []
    bare: list[int] = []
    for step in plan.steps:
        captured_detail = (
            audit_input_snapshot.detail_for_step(step.id)
            if audit_input_snapshot is not None
            else None
        )
        if captured_detail is not None:
            on_disk = captured_detail.state != "missing"
        else:
            on_disk = resolve_detail_artifact(
                plan_path, plan, step, repo_root
            ).on_disk
        (detailed if on_disk else bare).append(step.id)
    return DetailBundleStatus(
        total=len(plan.steps),
        detailed_step_ids=tuple(detailed),
        bare_step_ids=tuple(bare),
    )


def _format_detail_bundle_status_block(status: DetailBundleStatus) -> str:
    """Render the grounding-honesty preamble for the detail bundle.

    Empty when every step has a detail file — the fully-grounded path is
    byte-for-byte unchanged. When some/all steps are bare, it states the
    real coverage and carries the bare-stage instructions: which findings not
    to raise for a step with no detail file, when a **Missing edge-case
    concept** gap counts (decomposition gaps only, not detail-prose remedies),
    and when observable-property coverage remains actionable.
    """
    if not status.is_bare:
        return ""
    bare = ", ".join(f"step {i}" for i in status.bare_step_ids)
    kind = "bare" if status.is_fully_bare else "partially-detailed"
    return "\n".join(
        [
            f"**Detail coverage: {status.detailed_count} of {status.total} "
            f"step(s) have a detail file authored — this is a {kind} plan.**",
            "",
            f"These steps have **no detail file yet** ({bare}). Audit them "
            "at the plan/concept level only: do **not** raise a "
            "detail-contradiction, detail-vs-code, or \"the detail omits X\" "
            "finding for a step that has no detail file — its absence is the "
            "expected pre-`detail` state, not a gap. Judge bare steps solely "
            "on the plan body's concepts and the code at HEAD. For a bare "
            "step, raise a **Missing edge-case concept** finding only when "
            "its `### Fix` sub-block is a new step or a new acceptance "
            "criterion — a decomposition gap this audit should catch. Skip "
            "it when the fix is \"specify it in the detail file\": `detail` "
            "has not run for that step yet, so naming it here does that "
            "stage's job for it.",
            "",
            "Keep named observable-property coverage at this bare stage: "
            "when the plan names an observable property, acceptance result, "
            "ownership boundary, safety guarantee, or ordering rule but "
            "provides no route that delivers it, raise a **Correctness** "
            "finding that names the missing property and route. Do **not** "
            "raise a Correctness or Completeness finding solely because a "
            "bare step has not selected a typed attachment or carrier, "
            "serializer, internal dependency ordering, fixture shape, "
            "telemetry value, parser arrangement, or similar internal "
            "delivery mechanism, even when the proposed choice is described "
            "as severe; leave that choice to `detail`. The only exception is "
            "an explicit plan text contract that makes a named mechanism "
            "observable for compatibility, safety, ordering, ownership, or "
            "bypass — do not infer that exception from a plausible "
            "implementation choice.",
            "",
        ]
    )


# The run-grade framing of ``prompts/plan-audit.md``'s detail-bundle section,
# held here verbatim so the default prompt is byte-for-byte what it was before
# the framing became a template variable.
_RUN_GRADE_BUNDLE_FRAMING = (
    "These are the per-step detail files a developer will implement against."
)


def _format_bundle_framing_block() -> str:
    """Return the conceptual framing for the run-grade detail bundle."""
    return (
        _RUN_GRADE_BUNDLE_FRAMING
    )


def _collapse_usable_audit_intent(value: Optional[str]) -> Optional[str]:
    """Collapse an intent, or ``None`` when it is a fence presence non-value.

    Matches ``_render_intent_section``'s omit path via the shared
    :func:`is_placeholder_intent`: empty / whitespace and all six TODO/TBD
    spellings drop out. That agreement is the point — what
    :func:`check_intent_presence` reports missing must render nowhere.
    """
    if value is None:
        return None
    collapsed = collapse_intent_to_one_line(value)
    if not collapsed or is_placeholder_intent(collapsed):
        return None
    return collapsed


def _format_intent_block(plan: Plan) -> str:
    """Render plan/step intents as authoritative scope input for the audit.

    Empty when no usable intent survives — the template then keeps the same
    prompt an intent-free plan already gets. Framing lives entirely in this
    string so the static template never mentions intent.
    """
    plan_intent = _collapse_usable_audit_intent(plan.intent)
    step_lines: list[str] = []
    for step in plan.steps:
        step_intent = _collapse_usable_audit_intent(step.intent)
        if step_intent is None:
            continue
        step_lines.append(
            f"- step {step.id} ({step.title}): {step_intent}"
        )
    if plan_intent is None and not step_lines:
        return ""
    lines = [
        "**Authoritative scope input (plan/step intent):**",
        "",
        "These lines are the positive half of the scope fence — the declared "
        "purpose that feeds this prompt's stay-inside-scope rule.",
        "",
    ]
    if plan_intent is not None:
        lines.append(f"- Plan intent: {plan_intent}")
    lines.extend(step_lines)
    lines.extend(
        [
            "",
            "Use this to decide whether a gap is inside the declared purpose. "
            "A gap outside it is `[out-of-scope-deferred]`, not a completeness "
            "finding. Do **not** audit the intent itself: do not compare it "
            "against Overview, `## Why`, a detail file, or code, and do not "
            "raise a finding that work disagrees with the stated intent.",
            "",
        ]
    )
    return "\n".join(lines)


# Canonical seed scope-contract fields carried into the audit prompt
# (BACKLOG #162), in presentation order. Heading keys normalize through
# ``split_body_sections``; only Out of scope has the direct-ingestion alias.
_SEED_SCOPE_CONTRACT_FIELDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("outcome",), "Outcome"),
    (("in scope",), "In scope"),
    (("out of scope / non-goals", "out of scope"), "Out of scope / Non-goals"),
    (("allowed behavior changes",), "Allowed behavior changes"),
    (("allowed reorganization",), "Allowed reorganization"),
    (("verification",), "Verification"),
    (("stop / defer",), "Stop / defer"),
)


def _extract_seed_scope_contract(seed_text: str) -> Optional[str]:
    """Return the seed's scope-contract fields, verbatim and labeled.

    ``None`` when the seed carries none of :data:`_SEED_SCOPE_CONTRACT_FIELDS`
    — a seed authored entirely outside the canonical field names leaves no
    contract to surface, rather than guess at one.
    """
    sections = split_body_sections(seed_text, ignore_fenced_code=True)
    blocks: list[str] = []
    for keys, label in _SEED_SCOPE_CONTRACT_FIELDS:
        body = next(
            (
                candidate
                for key in keys
                if (candidate := sections.get(key)) is not None and candidate.strip()
            ),
            None,
        )
        if body is None:
            continue
        blocks.append(f"**{label}:**\n\n{body.strip()}")
    if not blocks:
        return None
    return "\n\n".join(blocks)


def _format_scope_contract_block(
    plan: Plan,
    repo_root: Path,
    *,
    max_bytes: int = _MAX_PROMPT_FILE_BYTES,
    audit_input_snapshot=None,
) -> str:
    """Render the plan's originating seed scope contract for the audit prompt.

    Empty when the plan has no resolvable ``source_seed`` or the seed carries
    none of the canonical scope-contract fields — the prompt then renders
    byte-identical to a plan authored without this feature (BACKLOG #162).
    Informational only: the plan body remains authoritative on conflict, so
    a plan that has legitimately evolved past its seed is never fenced
    against its own history.

    ``audit_input_snapshot``, when given, supplies ``source_seed_bytes``
    captured once before a multi-pass ``--iterate`` audit rather than
    re-reading the seed from disk on every pass — the same frozen-input
    contract :func:`_format_audit_detail_bundle` and
    :func:`audit_detail_bundle_status` already honor for the detail bundle.

    Without a snapshot, resolution goes through
    :func:`plan_tool.review_persistence._read_source_seed_bytes`, whose
    archived-seed fallback matters here: ``create --from-existing``
    unconditionally moves its seed to ``archive/`` right after publishing
    the new plan, so the seed is already gone by the time any later
    ``completeness-audit`` run — the only caller of this no-snapshot path —
    reads it.
    """
    if not plan.source_seed:
        return ""
    if audit_input_snapshot is not None:
        seed_bytes = audit_input_snapshot.source_seed_bytes
    else:
        from plan_tool.review_persistence import _read_source_seed_bytes

        seed_bytes = _read_source_seed_bytes(plan, repo_root)
    if seed_bytes is None:
        return ""
    text = seed_bytes.decode("utf-8", errors="replace")
    contract = _extract_seed_scope_contract(text)
    if contract is None:
        return ""
    body, _truncated = clip_text_to_byte_budget(contract, max_bytes=max_bytes)
    return (
        "**Originating scope contract (from the plan's seed, "
        f"`{plan.source_seed}`) — informational; the plan body wins on "
        f"conflict:**\n\n{body}\n"
    )


def _format_carried_findings_block(
    carried: Sequence[CarriedFinding],
    *,
    max_findings: int = _CARRIED_BLOCK_MAX_FINDINGS,
) -> str:
    """Render the carried-finding section for ``prompts/plan-audit.md``.

    The accumulated findings are fed back to *guide later passes toward
    convergence*, not merely to dedupe: each pass gets the running
    coverage map (slug + severity + resolution + excerpt) so it re-uses
    established slugs for re-found gaps, concentrates effort on the areas
    earlier passes have not covered, and leaves already-resolved findings
    alone. Only anchored findings are rendered (the slug is the re-use
    identity); empty anchored input renders an empty string (first pass /
    no slugged findings yet) so the template line collapses to a blank.
    """
    anchored = [c for c in carried if c.anchor]
    if not anchored:
        return ""
    limit = max(0, max_findings)
    ordered = sorted(
        anchored,
        key=lambda c: (
            _carried_severity_rank(c.severity),
            c.resolution != CARRIED_RESOLUTION_OPEN,
            c.anchor or "",
            c.title,
        ),
    )
    selected = ordered[:limit]
    dropped = len(ordered) - len(selected)
    lines = [
        "",
        "**Findings established by earlier passes (converge against "
        "these):**",
        "",
        "These gaps are already on record for this plan — anchor slug,",
        "severity, resolution, and a short excerpt. Treat them as your",
        "running coverage map; the job of this pass is to move the audit",
        "toward convergence, not to re-derive what is already known:",
        "",
        "- Reuse identities: if a gap you find is conceptually one of",
        "  these, re-use its exact `[anchor-slug]` verbatim — your wording",
        "  may differ; the slug is the identity. Mint a new slug only for a",
        "  genuinely new concept. A re-found gap that re-uses its slug is",
        "  how the audit converges instead of logging the same gap twice.",
        "- Probe what these have NOT covered: concentrate this pass on the",
        "  steps, concepts, risks, and criteria untouched below — that is",
        "  where an unfound gap most likely still hides.",
        "- Leave the resolved alone: a finding marked `applied` or",
        "  `skipped` was already acted on; raise it again only if the plan",
        "  text shows the fix did not land.",
        "",
        "Convergence is the goal, not thoroughness theater: a pass that",
        "adds no new gap because the plan is genuinely sound is the success",
        "state — do not invent marginal gaps to look diligent. Equally,",
        "never suppress a real new gap to appear converged; a true gap",
        "found late still beats a false convergence.",
        "",
    ]
    for finding in selected:
        resolution = ""
        if finding.resolution != CARRIED_RESOLUTION_OPEN:
            resolution = f", {finding.resolution}"
            if finding.resolution_reason:
                resolution += f": {finding.resolution_reason}"
        lines.append(
            f"- `[{finding.anchor}]` "
            f"({finding.severity.upper()}{resolution}) — {finding.title} "
            f"[{confidence_label(finding.confidence)}]"
        )
        if finding.body_excerpt:
            lines.append(f"  excerpt: {finding.body_excerpt}")
    if dropped:
        lines.append(
            f"… {dropped} more lower-priority finding(s) not shown "
            f"(cap {limit})."
        )
    lines.append("")
    return "\n".join(lines)


def render_plan_audit_prompt(
    plan: Plan,
    plan_path: Path,
    *,
    repo_root: Path,
    carried_findings: Sequence[CarriedFinding] = (),
    collect_blocks: Optional[list[tuple[str, int]]] = None,
    audit_input_snapshot=None,
) -> Optional[str]:
    """Render ``prompts/plan-audit.md`` for this plan.

    Returns ``None`` (caller skips the claude call) only when the plan
    has no body to audit — every authored plan with content is a valid
    target, regardless of how many steps are DONE.

    The rendered prompt embeds the per-step detail files (the
    implementation bundle) via :func:`_format_audit_detail_bundle` so the
    conceptual audit can see what the design already specifies and stop
    re-flagging gaps the detail files already cover.

    ``carried_findings`` — accumulated findings from earlier passes —
    renders the convergence-guidance block
    (:func:`_format_carried_findings_block`) with severity, resolution,
    and excerpt context so a multi-pass audit keeps ids stable, steers
    each pass toward the gaps earlier passes have not covered, and drives
    itself toward convergence instead of re-deriving known findings.

    Plan and step ``intent`` fields render via :func:`_format_intent_block`
    as authoritative scope input for the stay-inside-scope rule; absent or
    placeholder intents leave that slot empty so the prompt stays unchanged.

    ``plan.source_seed`` (set by ``create --from-existing``, BACKLOG #162)
    resolves to its originating seed's scope-contract fields via
    :func:`_format_scope_contract_block`; a plan with no resolvable seed
    renders this slot empty, so the prompt stays byte-identical to before
    the feature existed.
    """
    if audit_input_snapshot is not None:
        plan = audit_input_snapshot.plan
        body = audit_input_snapshot.plan_body.strip() or None
    else:
        body = _collect_plan_body(plan_path)
    if body is None:
        return None
    template_path = prompts_dir() / "plan-audit.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    status = audit_detail_bundle_status(
        plan,
        plan_path,
        repo_root,
        audit_input_snapshot=audit_input_snapshot,
    )
    detail_bundle_status_rendered = _format_detail_bundle_status_block(status)
    detail_files_rendered = _format_audit_detail_bundle(
        plan,
        plan_path,
        repo_root,
        max_file_bytes=_MAX_PROMPT_FILE_BYTES,
        audit_input_snapshot=audit_input_snapshot,
    )
    scope_contract_rendered = _format_scope_contract_block(
        plan, repo_root, audit_input_snapshot=audit_input_snapshot
    )
    intent_rendered = _format_intent_block(plan)
    project_context_rendered = (
        audit_input_snapshot.project_context
        if audit_input_snapshot is not None
        else project_profile_context(repo_root)
    )
    # ``${intent_block}${scope_contract_block}`` sit on one template line with
    # no separator (so either slot alone stays byte-identical to before the
    # other existed). When BOTH render, that concatenation merges the scope
    # contract's bold header into the intent block's last sentence as one
    # markdown paragraph instead of two sections — add the missing blank
    # line here, the one place that knows both slots are non-empty.
    scope_contract_joined = (
        "\n" + scope_contract_rendered
        if intent_rendered and scope_contract_rendered
        else scope_contract_rendered
    )
    if collect_blocks is not None:
        # Reuse the just-built strings so the budget advisory sizes its blocks
        # without a second formatter pass; the leaf sorts by size, order free.
        collect_blocks.extend([
            ("plan body", len(body.encode("utf-8"))),
            ("detail bundle", len(detail_files_rendered.encode("utf-8"))),
            ("detail-bundle status",
             len(detail_bundle_status_rendered.encode("utf-8"))),
            ("scope contract", len(scope_contract_rendered.encode("utf-8"))),
        ])
        if project_context_rendered:
            collect_blocks.append(
                ("project-context", len(project_context_rendered.encode("utf-8")))
            )
    return template.safe_substitute(
        plan_title=plan.title,
        plan_body_block=body,
        detail_bundle_framing_block=_format_bundle_framing_block(),
        detail_bundle_status_block=detail_bundle_status_rendered,
        detail_files_block=detail_files_rendered,
        carried_findings_block=_format_carried_findings_block(
            carried_findings
        ),
        intent_block=intent_rendered,
        scope_contract_block=scope_contract_joined,
        project_context_block=render_project_context_block(
            project_context_rendered
        ),
        response_format_block=_PLAN_AUDIT_RESPONSE_CONTRACT.render_prompt_block(),
    )


# Collapses a finding body to a lowercase alphanumeric skeleton for the
# fallback id fingerprint. When claude omits the prompt's ``[anchor-slug]``
# contract, hashing the raw body mints a fresh id on every reword; hashing
# the normalized skeleton instead means trivial rephrasings (punctuation,
# casing, whitespace) map to the same id so the convergence loop and the
# multi-sample union still dedupe them.
_AUDIT_FP_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_audit_fingerprint(body: str) -> str:
    """Lowercase + collapse non-alphanumerics to single spaces, trimmed."""
    return _AUDIT_FP_NORMALIZE_RE.sub(" ", body.lower()).strip()


# The headings the prompt must emit. A heading with ``_(none)_`` underneath
# is a valid empty layer; omitting it is malformed.
_PLAN_AUDIT_REQUIRED_HEADINGS = _PLAN_AUDIT_RESPONSE_CONTRACT.required_headings

# Appended to the prompt on the one retry when a required layer heading is
# absent. Mirrors detail's ``_REPROMPT_SUFFIX`` one-retry recovery: spell
# out the exact contract so claude self-corrects without re-deriving it.
_PLAN_AUDIT_REPROMPT_SUFFIX = (
    "\n\n---\n\n"
    "**Your previous response omitted a required findings section.** "
    "Re-emit the required sections as the last sections of your response, "
    "even when a layer has nothing to report:\n\n"
    + _PLAN_AUDIT_RESPONSE_CONTRACT.render_empty_skeleton()
    + "\n\n"
    "Replace `_(none)_` with severity bullets where you do have findings, "
    "keeping the `[anchor-slug] [audit-step:N]` prefix when one committed "
    "non-done step owns the finding, and the trailing "
    "`(impact=…, complexity=…)` tag on each."
)


@dataclass(frozen=True)
class _AuditTagObservation:
    """One per-sample attribution observation keyed by stable finding ID."""

    finding_id: str
    target_step_id: Optional[int]


PASS_OUTCOME_CONFORMING = "conforming"
PASS_OUTCOME_FAILED_OR_MALFORMED = "failed_or_malformed"
PASS_OUTCOME_SKIPPED = "skipped"
PASS_OUTCOME_TERMINAL_PLAN_QUOTA = "terminal_plan_quota"


@dataclass(frozen=True)
class _AuditSampleEvidence:
    """Ephemeral result of a plan-audit response for advisory evaluation."""

    advisory_valid: bool
    pass_outcome: str = PASS_OUTCOME_SKIPPED
    observations: tuple[_AuditTagObservation, ...] = ()


def _parse_plan_audit_findings_with_evidence(
    stdout: str,
    *,
    valid_audit_target_ids: frozenset[int] = frozenset(),
) -> tuple[
    list[Recommendation],
    frozenset[str],
    int,
    tuple[_AuditTagObservation, ...],
    int,
]:
    """Parse ordinary findings plus separate, non-routing tag observations.

    Returns ``(recs, present_headings, sluggless_count, observations,
    high_impact_coerced)``. ``high_impact_coerced`` counts unlabelled
    ``impact=high`` findings that received ``high`` as a fallback severity.
    """
    from plan_tool.launcher import _ANSI_RE

    clean = _ANSI_RE.sub("", stdout)
    present = frozenset(
        m.group(1).lower() for m in _PLAN_AUDIT_SECTION_RE.finditer(clean)
    )
    recs: list[Recommendation] = []
    observations: list[_AuditTagObservation] = []
    sluggless = 0
    high_impact_coerced = 0
    for section in _PLAN_AUDIT_RESPONSE_CONTRACT.sections:
        for bullet in _findings_under_heading(stdout, section.heading):
            raw_sev, body = _recover_severity_from_body(
                bullet.severity, bullet.body
            )
            sev = _CLAUDE_SEVERITY_MAP.get(raw_sev, "info")
            target, without_tag = _split_audit_step_evidence(
                body, valid_target_ids=valid_audit_target_ids
            )
            # Prefer the prompt's stable ``[anchor-slug]`` as the id
            # fingerprint so a re-audit that re-phrases the same concept
            # maps to the same id (the convergence loop keys off ids).
            key, body = _split_audit_key(without_tag)
            # Misshape ``HIGH `[slug]`: prose`` leaves a separator colon
            # after the wrapped slug; strip it so the title is clean.
            if key and body.startswith((":", "-")):
                body = body[1:].lstrip()
            # Pull the trailing ``### Restated`` / ``### Fix`` sub-blocks so
            # the walk can show the user what apply will do and
            # ``apply_finding`` can steer claude to that exact edit. Split
            # BEFORE triage: the sub-blocks trail the WHOLE bullet
            # (including its triage tag), so extracting them first leaves a
            # clean "gap prose + tag" region for the triage-tag search below
            # to run over -- and BEFORE the fingerprint so neither wording
            # can destabilize the id.
            restated, fix, body = _split_audit_restated_and_fix(body)
            # Pull the (now-innermost) ``(impact=…, complexity=…)`` triage
            # tag so the apply loop can defer low-impact/high-complexity
            # conceptual gaps instead of auto-applying every finding.
            impact, complexity, body = _split_triage_tags(body)
            # ``restated_property`` is meaningful only on the Correctness
            # axis (plan-audit.md's property-coverage rule never asks a
            # Completeness finding for one) -- discard a stray marker the
            # model attaches to a Completeness bullet instead of persisting
            # it, since the field's own contract promises ``None`` there.
            if section.key != "plan-correctness":
                restated = None
            # Extraction-failure guard: an unlabelled high-impact finding
            # may have a severity token still parked in its body. Re-attempt
            # that recovery before treating the missing label as high. An
            # explicit advisory prefix is a valid, independent severity
            # judgment and must remain untouched.
            severity_established = raw_sev != "UNSPECIFIED"
            if (
                not severity_established
                and impact == "high"
                and sev in _ADVISORY_SEVERITIES
            ):
                rescued_sev, rescued_body = _recover_severity_from_body(
                    "UNSPECIFIED", body
                )
                if rescued_sev != "UNSPECIFIED":
                    sev = _CLAUDE_SEVERITY_MAP.get(rescued_sev, sev)
                    severity_established = True
                    key2, rescued_body = _split_audit_key(rescued_body)
                    if key2 and not key:
                        key = key2
                    if key2 and rescued_body.startswith((":", "-")):
                        rescued_body = rescued_body[1:].lstrip()
                    body = rescued_body
            # If the finding was unlabelled even after recovery, use the
            # high-impact tag as its fallback severity. Explicit/recovered
            # labels always win.
            sev, coerced = _enforce_high_impact_severity(
                sev,
                impact,
                severity_established=severity_established,
            )
            if coerced:
                high_impact_coerced += 1
            if not key:
                sluggless += 1
            # Fallback to the normalized skeleton (not the raw body) so a
            # reworded-but-equivalent finding still hashes to the same id.
            fingerprint = key or _normalize_audit_fingerprint(body) or body
            rec = Recommendation(
                id=_make_rec_id(None, section.key, fingerprint),
                source=section.key,
                severity=sev,
                step_id=None,
                title=(body.splitlines()[0][:120] if body else "(unspecified)"),
                body=body,
                suggested_action=fix,
                impact=impact,
                complexity=complexity,
                anchor=key,
                restated_property=restated,
            )
            recs.append(rec)
            observations.append(_AuditTagObservation(rec.id, target))
    return recs, present, sluggless, tuple(observations), high_impact_coerced


def _parse_plan_audit_findings(
    stdout: str,
) -> tuple[list[Recommendation], frozenset[str], int, int]:
    """Parse the audit response's two finding sections.

    Returns ``(recs, present_headings, sluggless_count, high_impact_coerced)``
    where ``present_headings`` is the lowercased set of ``## … findings``
    headings the response actually emitted (so the caller can tell a
    valid empty ``_(none)_`` layer from a wholly-absent one),
    ``sluggless_count`` is how many findings omitted the ``[anchor-slug]``
    contract (visibility into id-stability drift), and
    ``high_impact_coerced`` is how many unlabelled ``impact=high`` findings
    received ``high`` as a fallback severity.
    """
    recs, present, sluggless, _observations, coerced = (
        _parse_plan_audit_findings_with_evidence(stdout)
    )
    return recs, present, sluggless, coerced


def check_plan_audit(
    plan: Plan,
    plan_path: Path,
    *,
    repo_root: Path,
    invoker: Optional[PlanAuditInvoker] = None,
    log_file=None,
    carried_findings: Sequence[CarriedFinding] = (),
    audit_input_snapshot=None,
    _sample_evidence_out: Optional[list[_AuditSampleEvidence]] = None,
) -> list[Recommendation]:
    """Audit the plan's concepts for correctness, completeness, and clarity.

    One claude call (a second, only when the first response omits a
    required ``## … findings`` heading — see
    :data:`_PLAN_AUDIT_REQUIRED_HEADINGS`). Parses the prompt's two
    finding sections and tags each list with its own source so the report
    routes them into the right group. Material ambiguity is deliberately
    emitted under correctness, preserving the two-source report contract:

    - ``source="plan-correctness"`` — unsound, contradictory, wrong, or
      materially ambiguous concepts (rendered in the correctness group; can
      be critical/high).
    - ``source="plan-completeness"`` — orphaned concepts, uncovered
      risks, dangling criteria, missing edge cases (advisory group).

    Returns ``[]`` (no claude call attempted) when ``invoker`` is
    ``None``, the plan has no body, or the invoker raises / exits
    non-zero. A one-line ``plan-tool: plan-audit: ...`` summary is
    written to ``log_file`` (default stderr) on every call so CI
    operators can confirm the pass ran.

    ``carried_findings`` — accumulated findings from earlier samples —
    is forwarded to :func:`render_plan_audit_prompt` so a multi-sample
    caller (:func:`audit_plan_until_stable`) can have re-found concepts
    re-use their established slug while also seeing severity,
    resolution, and excerpt context.
    """
    out = log_file if log_file is not None else sys.stderr

    def _record_sample(sample: _AuditSampleEvidence) -> None:
        if _sample_evidence_out is not None:
            _sample_evidence_out.append(sample)

    def _log_skip(reason: str) -> None:
        tool(f"plan-audit: skipped ({reason})", stream=out)

    if invoker is None:
        _log_skip("no invoker configured")
        _record_sample(
            _AuditSampleEvidence(False, pass_outcome=PASS_OUTCOME_SKIPPED)
        )
        return []
    rendered_plan = (
        audit_input_snapshot.plan
        if audit_input_snapshot is not None
        else plan
    )
    prompt = render_plan_audit_prompt(
        rendered_plan,
        plan_path,
        repo_root=repo_root,
        carried_findings=carried_findings,
        audit_input_snapshot=audit_input_snapshot,
    )
    if prompt is None:
        _log_skip("plan has no body to audit")
        _record_sample(
            _AuditSampleEvidence(False, pass_outcome=PASS_OUTCOME_SKIPPED)
        )
        return []

    # One retry when a required layer heading is absent (#3) — a missing
    # section means a whole audit layer was dropped, which a fresh prompt
    # with the conformance reminder usually recovers. A heading present
    # with ``_(none)_`` is a valid empty layer and does NOT retry.
    recs: list[Recommendation] = []
    sluggless = 0
    high_impact_coerced = 0
    observations: tuple[_AuditTagObservation, ...] = ()
    present: frozenset[str] = frozenset()
    valid_target_ids = frozenset(
        step.id
        for step in rendered_plan.steps
        if step.scope is StepScope.COMMITTED and step.status is not StepStatus.DONE
    )
    attempt_prompt = prompt
    for attempt in (1, 2):
        try:
            invocation = invoker(attempt_prompt)
            exit_code, stdout, failure_kind = _plan_audit_invocation_parts(
                invocation
            )
        except Exception as exc:  # noqa: BLE001 — claude shell-out can fail many ways
            _log_skip(f"invoker raised: {exc!r}")
            _record_sample(
                _AuditSampleEvidence(
                    False,
                    pass_outcome=PASS_OUTCOME_FAILED_OR_MALFORMED,
                )
            )
            return []
        if exit_code != 0:
            # 127 is the not-on-PATH convention; any other code is a real
            # claude failure — surface the response tail so the operator
            # can tell a usage-limit / max-turns abort from a missing
            # binary instead of guessing from a discarded stdout.
            if exit_code == 127:
                _log_skip("claude not found on PATH (exit 127)")
            else:
                tail = " ".join(stdout.strip().split())[-200:]
                _log_skip(
                    f"invoker exited non-zero (code {exit_code})"
                    + (f"; response tail: …{tail}" if tail else "")
                )
            _record_sample(
                _AuditSampleEvidence(
                    False,
                    pass_outcome=(
                        PASS_OUTCOME_TERMINAL_PLAN_QUOTA
                        if failure_kind is ClaudeFailureKind.PLAN_QUOTA
                        else PASS_OUTCOME_FAILED_OR_MALFORMED
                    ),
                )
            )
            return []
        (
            recs,
            present,
            sluggless,
            observations,
            high_impact_coerced,
        ) = _parse_plan_audit_findings_with_evidence(
            stdout, valid_audit_target_ids=valid_target_ids
        )
        missing = _PLAN_AUDIT_REQUIRED_HEADINGS - present
        if not missing or attempt == 2:
            break
        tool(
            f"plan-audit: response missing layer heading(s) "
            f"{sorted(missing)}; re-prompting once for both sections",
            stream=out,
        )
        attempt_prompt = prompt + _PLAN_AUDIT_REPROMPT_SUFFIX

    headings_complete = not (_PLAN_AUDIT_REQUIRED_HEADINGS - present)
    _record_sample(
        _AuditSampleEvidence(
            advisory_valid=headings_complete,
            pass_outcome=(
                PASS_OUTCOME_CONFORMING
                if headings_complete
                else PASS_OUTCOME_FAILED_OR_MALFORMED
            ),
            observations=observations if headings_complete else (),
        )
    )

    n_corr = sum(1 for r in recs if r.source == "plan-correctness")
    n_comp = sum(1 for r in recs if r.source == "plan-completeness")
    # Conformance visibility, parallel to ``sluggless`` for the slug
    # contract: how many findings omitted the ``### Fix`` targeted-fix
    # sub-block. A fixless finding still applies (the gap body drives it),
    # but the walk can't show "what apply will do", so surface the drift to
    # the operator the same way a missing slug is surfaced.
    fixless = sum(1 for r in recs if r.suggested_action is None)
    contract_notes = []
    if sluggless:
        contract_notes.append(f"{sluggless} missing [anchor-slug]")
    if fixless:
        contract_notes.append(f"{fixless} missing ### Fix")
    if high_impact_coerced:
        contract_notes.append(
            f"{high_impact_coerced} impact=high severity coerced to high"
        )
    contract_note = f" ({', '.join(contract_notes)})" if contract_notes else ""
    tool(
        f"plan-audit: {n_corr} correctness + "
        f"{n_comp} completeness finding(s){contract_note}",
        stream=out,
    )
    return recs


# Defaults for :func:`audit_plan_until_stable`. Each conceptual-audit *pass*
# is a full, independent audit over the whole plan + code at HEAD — it reads
# the same inputs every time, so a pass re-rolls the LLM's non-determinism
# rather than covering a new subset. A single pass therefore captures only a
# subset of the stable finding set (the report saw 6 findings one run, 3 the
# next); running multiple passes and unioning by stable id captures the set
# one report can show. The loop keeps running while a pass's marginal-new
# count stays at or above ``new_threshold`` (productive), stops after
# ``dry_rounds`` consecutive non-productive passes, and is bounded by the
# ``max_passes`` hard cap. The default ``dry_rounds`` is 1 — a single zero-new
# pass stops the loop; raise it (``--audit-dry-rounds 2+``) to require a streak
# of confirming dry passes and absorb the LLM's per-pass non-determinism (one
# dry pass treated as noise, a streak as the real convergence signal).
AUDIT_DEFAULT_MAX_PASSES = 3
AUDIT_DEFAULT_DRY_ROUNDS = 1
AUDIT_DEFAULT_NEW_THRESHOLD = 1
_SAMPLER_CHECKPOINT_NAME = "in-progress-sampler-checkpoint"
# The sampler inputs gated on before a checkpoint may resume, shared between
# the writer and the reader so the two can't drift independently. Deliberately
# excludes the calibration lookup — see DATA_CONTRACT.md's "Sampler
# checkpoints".
_SAMPLER_IDENTITY_FIELDS = (
    "audit_input_fingerprint",
    "max_passes",
    "dry_rounds",
    "new_threshold",
    "backend_name",
    "resolved_model",
)

# BACKLOG #125 — a pass whose new findings are all non-blocking (per
# ``convergence.is_blocking``) is diminishing return, not real coverage
# growth; see docs/how-to/pipeline/audit.md's "Severity-aware low-yield convergence".


def _checkpoint_plan_path(plan_path: Path, repo_root: Path) -> str:
    """Return the persisted plan path in the saved-review convention."""
    return _repo_relative_posix(plan_path.resolve(), repo_root.resolve())


def _serialized_low_impact_demotion_classes(
    lookup: object,
) -> Optional[list[dict[str, object]]]:
    """Serialize the frozen calibration rule when it exposes its cohorts."""
    finding_classes = getattr(lookup, "qualifying_finding_classes", None)
    if not isinstance(finding_classes, frozenset):
        return None
    try:
        return [
            dataclasses.asdict(finding_class)
            for finding_class in sorted(finding_classes)
        ]
    except (TypeError, ValueError):
        return None


def _restore_low_impact_demotion_lookup(value: object):
    """Rebuild the checkpoint's frozen calibration lookup, or reject it."""
    if not isinstance(value, list):
        return None
    from plan_tool.telemetry_analysis import FindingClass, LowImpactDemotionLookup

    fields = {field.name for field in dataclasses.fields(FindingClass)}
    finding_classes = []
    for item in value:
        if not isinstance(item, dict) or set(item) != fields:
            return None
        if not all(
            isinstance(item[name], str)
            for name in ("source", "anchor_category", "scope_shape")
        ) or not (
            item["purity_verdict_provenance"] is None
            or isinstance(item["purity_verdict_provenance"], str)
        ):
            return None
        finding_classes.append(FindingClass(**item))
    if len(set(finding_classes)) != len(finding_classes):
        return None
    return LowImpactDemotionLookup(frozenset(finding_classes))


def _sampler_resume_identity(
    *,
    audit_input_fingerprint: str,
    max_passes: int,
    dry_rounds: int,
    new_threshold: int,
    backend_name: str,
    resolved_model: Optional[str],
) -> dict[str, object]:
    """Return the sampler inputs gated on before a checkpoint may resume.

    See :data:`_SAMPLER_IDENTITY_FIELDS` for what this deliberately omits.
    """
    identity = {
        "audit_input_fingerprint": audit_input_fingerprint,
        "max_passes": max_passes,
        "dry_rounds": dry_rounds,
        "new_threshold": new_threshold,
        "backend_name": backend_name,
        "resolved_model": resolved_model,
    }
    assert set(identity) == set(_SAMPLER_IDENTITY_FIELDS)
    return identity


@dataclass(frozen=True)
class _RestoredSamplerState:
    """A complete, validated sampler boundary ready for the next pass."""

    by_id: dict[str, Recommendation]
    materiality_by_id: dict[str, bool]
    observations_by_id: dict[str, list[tuple[int, Optional[int]]]]
    passes: int
    consecutive_dry: int
    conforming_pass_count: int
    failed_or_malformed_pass_count: int
    stopped_on_dry: bool
    dry_streak_grew: bool
    dry_streak_unconfirmed_growth: bool
    dry_streak_low_yield: bool
    advisory_invalid: bool
    early_stop_reason: Optional[str]
    terminal_reason: Optional[str]
    low_impact_demotion_lookup: object


def _restore_sampler_checkpoint_state(
    saved_review: object,
    *,
    expected_identity: Mapping[str, object],
    expected_code_fingerprint: Optional[dict[str, str]],
) -> tuple[Optional[_RestoredSamplerState], str]:
    """Restore one exact sampler boundary, or explain why it cannot resume."""
    if not getattr(saved_review, "is_in_progress_sampler_checkpoint", False):
        return None, "not-resumable"
    state = getattr(saved_review, "sampler_state", None)
    if not isinstance(state, dict):
        return None, "malformed"
    recorded_identity = state.get("identity")
    identity_fields = set(_SAMPLER_IDENTITY_FIELDS)
    if (
        not isinstance(recorded_identity, dict)
        or set(recorded_identity) != identity_fields
        or not isinstance(recorded_identity["audit_input_fingerprint"], str)
        or not recorded_identity["audit_input_fingerprint"]
        or any(
            isinstance(recorded_identity[name], bool)
            or not isinstance(recorded_identity[name], int)
            for name in ("max_passes", "dry_rounds", "new_threshold")
        )
        or not isinstance(recorded_identity["backend_name"], str)
        or not recorded_identity["backend_name"]
        or not (
            recorded_identity["resolved_model"] is None
            or isinstance(recorded_identity["resolved_model"], str)
        )
    ):
        return None, "malformed"
    if recorded_identity != expected_identity:
        return None, "identity-mismatch"
    if (
        expected_code_fingerprint is None
        or not getattr(saved_review, "code_fingerprint_present", False)
        or getattr(saved_review, "code_fingerprint", None)
        != expected_code_fingerprint
    ):
        return None, "identity-mismatch"

    recommendations = getattr(saved_review, "recommendations", None)
    if not isinstance(recommendations, list):
        return None, "malformed"
    by_id: dict[str, Recommendation] = {}
    for recommendation in recommendations:
        if (
            not isinstance(recommendation, Recommendation)
            or not isinstance(recommendation.id, str)
            or not recommendation.id
            or recommendation.id in by_id
        ):
            return None, "malformed"
        by_id[recommendation.id] = recommendation

    def nonnegative_int(name: str) -> Optional[int]:
        value = state.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    passes = nonnegative_int("passes")
    consecutive_dry = nonnegative_int("consecutive_dry")
    conforming_pass_count = nonnegative_int("conforming_pass_count")
    failed_or_malformed_pass_count = nonnegative_int(
        "failed_or_malformed_pass_count"
    )
    if (
        passes is None
        or consecutive_dry is None
        or conforming_pass_count is None
        or failed_or_malformed_pass_count is None
        # Corruption-detection cross-check, not redundant: "next_pass" must
        # agree with "passes" — see _sampler_checkpoint_state's comment.
        or nonnegative_int("next_pass") != passes + 1
        or conforming_pass_count + failed_or_malformed_pass_count > passes
    ):
        return None, "malformed"

    materiality = state.get("materiality_by_id")
    if (
        not isinstance(materiality, dict)
        or set(materiality) != set(by_id)
        or any(
            not isinstance(rec_id, str) or not isinstance(value, bool)
            for rec_id, value in materiality.items()
        )
    ):
        return None, "malformed"

    observations = state.get("observations_by_id")
    if not isinstance(observations, dict) or not set(observations).issubset(by_id):
        return None, "malformed"
    restored_observations: dict[str, list[tuple[int, Optional[int]]]] = {}
    for rec_id, entries in observations.items():
        if not isinstance(rec_id, str) or not isinstance(entries, list):
            return None, "malformed"
        restored_entries: list[tuple[int, Optional[int]]] = []
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2:
                return None, "malformed"
            pass_number, target_step_id = entry
            if (
                isinstance(pass_number, bool)
                or not isinstance(pass_number, int)
                or pass_number < 1
                or pass_number > passes
                or (
                    target_step_id is not None
                    and (
                        isinstance(target_step_id, bool)
                        or not isinstance(target_step_id, int)
                    )
                )
            ):
                return None, "malformed"
            restored_entries.append((pass_number, target_step_id))
        restored_observations[rec_id] = restored_entries

    boolean_fields = (
        "stopped_on_dry",
        "dry_streak_grew",
        "dry_streak_unconfirmed_growth",
        "dry_streak_low_yield",
        "advisory_invalid",
    )
    if any(not isinstance(state.get(name), bool) for name in boolean_fields):
        return None, "malformed"
    if (
        state.get("lifecycle") != "in-progress"
        or state["stopped_on_dry"]
        or "early_stop_reason" not in state
        or state["early_stop_reason"] is not None
        or "terminal_reason" not in state
        or state["terminal_reason"] is not None
    ):
        return None, "malformed"
    demotion_lookup = _restore_low_impact_demotion_lookup(
        state.get("low_impact_demotion_classes")
    )
    if demotion_lookup is None:
        return None, "malformed"
    return (
        _RestoredSamplerState(
            by_id=by_id,
            materiality_by_id=dict(materiality),
            observations_by_id=restored_observations,
            passes=passes,
            consecutive_dry=consecutive_dry,
            conforming_pass_count=conforming_pass_count,
            failed_or_malformed_pass_count=failed_or_malformed_pass_count,
            stopped_on_dry=state["stopped_on_dry"],
            dry_streak_grew=state["dry_streak_grew"],
            dry_streak_unconfirmed_growth=state[
                "dry_streak_unconfirmed_growth"
            ],
            dry_streak_low_yield=state["dry_streak_low_yield"],
            advisory_invalid=state["advisory_invalid"],
            early_stop_reason=state["early_stop_reason"],
            terminal_reason=state["terminal_reason"],
            low_impact_demotion_lookup=demotion_lookup,
        ),
        "resumed",
    )


def _sampler_checkpoint_state(
    *,
    lifecycle: str,
    identity: Mapping[str, object],
    passes: int,
    consecutive_dry: int,
    materiality_by_id: Mapping[str, bool],
    observations_by_id: Mapping[str, list[tuple[int, Optional[int]]]],
    conforming_pass_count: int,
    failed_or_malformed_pass_count: int,
    stopped_on_dry: bool,
    dry_streak_grew: bool,
    dry_streak_unconfirmed_growth: bool,
    dry_streak_low_yield: bool,
    advisory_invalid: bool,
    early_stop_reason: Optional[str],
    terminal_reason: Optional[str],
    low_impact_demotion_classes: Optional[list[dict[str, object]]],
) -> dict[str, object]:
    """Return the complete cross-pass state after one logical sampler pass."""
    return {
        "lifecycle": lifecycle,
        "identity": dict(identity),
        # Derivable from "passes" and cross-checked against it on restore —
        # deliberate corruption detection, not redundant state.
        "next_pass": passes + 1,
        "passes": passes,
        "consecutive_dry": consecutive_dry,
        "materiality_by_id": dict(materiality_by_id),
        "observations_by_id": {
            rec_id: [list(observation) for observation in observations]
            for rec_id, observations in observations_by_id.items()
        },
        "conforming_pass_count": conforming_pass_count,
        "failed_or_malformed_pass_count": failed_or_malformed_pass_count,
        "stopped_on_dry": stopped_on_dry,
        "dry_streak_grew": dry_streak_grew,
        "dry_streak_unconfirmed_growth": dry_streak_unconfirmed_growth,
        "dry_streak_low_yield": dry_streak_low_yield,
        "advisory_invalid": advisory_invalid,
        "early_stop_reason": early_stop_reason,
        "terminal_reason": terminal_reason,
        "low_impact_demotion_classes": low_impact_demotion_classes,
    }


def _save_sampler_checkpoint(**kwargs) -> Path:
    """Defer the persistence import because its saved-review model imports us."""
    from plan_tool.review_persistence import save_sampler_checkpoint

    return save_sampler_checkpoint(**kwargs)


def _sampler_checkpoint_path(plan_path: Path) -> Path:
    """Return the stable sampler artifact path without importing at module load."""
    from plan_tool.review_persistence import sampler_checkpoint_path

    return sampler_checkpoint_path(plan_path)


def _sampler_checkpoint_is_terminal_residue(plan_path: Path) -> bool:
    """Return whether the stable artifact proves a terminal transition published."""
    from plan_tool.review_persistence import load_sampler_checkpoint

    try:
        loaded = load_sampler_checkpoint(plan_path)
    except OSError:
        return False
    return bool(
        loaded.review is not None
        and loaded.review.sampler_state is not None
        and loaded.review.sampler_state.get("lifecycle") == "terminal-residue"
    )


def _remove_sampler_checkpoint(path: Path) -> None:
    """Remove a published terminal residue after the non-resumable transition."""
    from plan_tool.checkpoint import discard_checkpoint

    discard_checkpoint(path)


def _checkpoint_payload_bytes(path: Path) -> int:
    """Read payload bytes for existing checkpoint telemetry without affecting audit flow."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _make_reporting_invoker(
    invoker: PlanAuditInvoker,
    reporter: ProgressReporter,
    pass_idx: int,
    pass_total: int,
) -> PlanAuditInvoker:
    """Wrap *invoker* so each claude call renders a start line, a
    periodic ``Ns elapsed`` heartbeat, and a done/FAILED line via
    *reporter* (stderr). The conceptual-audit calls run for minutes
    each; without this the operator sees nothing until the pass's
    findings return. :func:`check_plan_audit` may invoke twice for one
    pass (the missing-heading re-prompt); each attempt gets its own
    step line so the elapsed clock visibly restarts instead of silently
    doubling.
    """
    attempt = 0

    def _invoke(prompt: str) -> PlanAuditInvokerResult:
        nonlocal attempt
        attempt += 1
        label = f"conceptual audit pass {pass_idx}"
        if attempt > 1:
            label += f" (attempt {attempt})"
        handle = reporter.start_step(
            pass_idx,
            pass_total,
            label,
            attempt=attempt,
            prompt_bytes=len(prompt.encode("utf-8")),
        )
        start = time.monotonic()
        try:
            invocation = invoker(prompt)
        except Exception as exc:  # noqa: BLE001 — close the heartbeat, then re-raise for check_plan_audit's handler
            handle.fail(time.monotonic() - start, f"invoker raised: {exc!r}")
            raise
        exit_code, stdout, _failure_kind = _plan_audit_invocation_parts(
            invocation
        )
        elapsed = time.monotonic() - start
        if exit_code == 0:
            handle.complete(elapsed, len(stdout.encode("utf-8")))
        else:
            handle.fail(elapsed, f"claude exit {exit_code}")
        return invocation

    return _invoke


def audit_plan_until_stable(
    plan: Plan,
    plan_path: Path,
    *,
    repo_root: Path,
    invoker: Optional[PlanAuditInvoker] = None,
    max_passes: int = AUDIT_DEFAULT_MAX_PASSES,
    dry_rounds: int = AUDIT_DEFAULT_DRY_ROUNDS,
    new_threshold: int = AUDIT_DEFAULT_NEW_THRESHOLD,
    log_file=None,
    reporter: Optional[ProgressReporter] = None,
    run_logger=None,
    budget_report: Optional[dict] = None,
    advisory_out: Optional[list[Optional[AuditShapeAdvisory]]] = None,
    audit_input_snapshot=None,
    resumed_out: Optional[list[bool]] = None,
) -> list[Recommendation]:
    """Run :func:`check_plan_audit` repeatedly and union the findings by
    stable id, capturing the conceptual layer's stable set in one report.

    Each *pass* is a full, independent audit over the whole plan + code at
    HEAD; extra passes re-roll the LLM's non-determinism, not the inputs.
    Keeps running while a pass is *productive*: its marginal-new count
    clears ``new_threshold`` (default 1) and at least one new finding is
    material (``convergence.is_blocking_impact``). Stops after ``dry_rounds``
    consecutive non-productive passes, or at ``max_passes`` — whichever
    comes first. See docs/how-to/pipeline/audit.md's "Severity-aware low-yield
    convergence" (BACKLOG #125) for the full productive/non-productive
    rules, the two-pass low-yield floor, and the ``confirmation_kind``
    verdict (``budget_report["confirmation_kind"]``: ``"confirmed-dry"`` /
    ``"confirmed-low-yield"`` / ``None``).

    Union (not intersection): a finding that appears in *any* pass is
    kept, so a real gap one pass missed still lands. The slug-derived
    stable id (:func:`_make_rec_id` keyed on the prompt's
    ``[anchor-slug]``) makes the dedupe reliable across the re-phrasing
    that defeats a content hash. First occurrence wins, preserving the
    earliest pass's wording.

    Each pass after the first sees the accumulated anchored findings
    already collected (``carried_findings`` → the prompt's convergence-
    guidance block). This both keeps ids stable — a re-found concept
    re-uses its established slug instead of minting a fresh one, so the
    union collapses semantic duplicates and the dry-round counter stays
    honest (a rephrased duplicate no longer counts as "new" and resets
    it) — and steers each pass toward the steps/concepts/risks earlier
    passes have not covered, so the audit drives itself to convergence
    rather than re-deriving known gaps.

    ``reporter`` (when given) wraps every claude call in a start line +
    heartbeat + done/FAILED line via :func:`_make_reporting_invoker`, and
    a per-pass union line lands after each pass so the operator can
    watch the finding set converge. ``None`` keeps the legacy silent
    calls (tests, callers that own their own progress display).

    An errored pass (the invoker raises or exits non-zero) is *neutral*:
    it never advances the consecutive-dry counter and never triggers the
    dry-stop, so a flaky audit can't masquerade as convergence. It still
    counts against the ``max_passes`` budget so a persistently failing
    invoker can't loop unbounded, and each errored pass emits a warning.
    The audit-only adapter marks a terminal plan quota as the exception:
    that attempted pass ends this invocation's conceptual sampling early.

    When the loop stops without a clean confirmation, it emits a one-line
    "coverage budget-limited, not converged" warning. The coverage record
    retains only facts about that stop; it does not infer an operator route
    from the pass-count series.

    Falls back to a single ``check_plan_audit`` call when
    ``max_passes <= 1`` (today's behavior). Returns ``[]`` when the
    underlying audit returns nothing (no invoker, no body, claude failed).
    """
    out = log_file if log_file is not None else sys.stderr
    if advisory_out is not None:
        advisory_out[:] = [None]
    if resumed_out is not None:
        resumed_out[:] = [False]
    supplied_snapshot = audit_input_snapshot is not None
    advisory_invalid = False
    if audit_input_snapshot is None:
        try:
            from plan_tool.review_persistence import AuditInputSnapshot

            audit_input_snapshot = AuditInputSnapshot.capture(
                plan_path, repo_root
            )
        except Exception:  # noqa: BLE001 — normal audit remains best-effort
            advisory_invalid = True
    if audit_input_snapshot is not None:
        if audit_input_snapshot.detail_grade != "run":
            raise ValueError("audit input snapshot grade does not match audit grade")
        plan = audit_input_snapshot.plan
    elif supplied_snapshot:
        # A caller that sampled unsuccessfully must not fall back to a second,
        # live plan/detail read under a different identity.
        return []
    by_id: dict[str, Recommendation] = {}
    materiality_by_id: dict[str, bool] = {}
    observations_by_id: dict[str, list[tuple[int, Optional[int]]]] = {}
    consecutive_dry = 0
    passes = 0
    cap = max(1, max_passes)
    conforming_pass_count = 0
    failed_or_malformed_pass_count = 0
    stopped_on_dry = False
    early_stop_reason: Optional[str] = None
    dry_streak_grew = False
    # BACKLOG #125 (docs/how-to/pipeline/audit.md): sibling streak flags, reset together
    # on a productive pass — ``_unconfirmed_growth`` for growth outside the
    # low-yield carve-out (below-threshold, material or not), ``_low_yield``
    # for the carve-out itself.
    dry_streak_unconfirmed_growth = False
    dry_streak_low_yield = False
    terminal_reason: Optional[str] = None
    # Prompt-budget advisory — warn once per audit run (before the pass loop),
    # not once per pass: every pass re-audits the same plan (only the bounded
    # carried-findings block grows), so a per-pass warn would nag near-identical
    # lines. Gate on a real send: ``invoker is None`` sends nothing, and a
    # ``None`` base prompt (no plan body) means ``check_plan_audit`` won't send.
    # Advisory-only and best-effort — never changes the unioned findings or the
    # exit path. See step-1 ``prompt_budget`` / step-2 ``record_prompt_budget``.
    #
    # The base advisory warns/records once (near-identical passes must not nag);
    # the carried-findings block is the only part that grows across passes, so a
    # per-pass danger-band check below (not a second warn/record) re-arms the
    # generic backstop as the net when growth pushes a pass into ``high``. A
    # *failed* base measurement also leaves ``audit_budget_covered`` False,
    # keeping the backstop for every pass.
    audit_budget_covered = False
    audit_base_bytes = 0
    audit_base_warned_high = False
    # Fire the growth re-arm (below) at most once per run — the carried block
    # only grows, so an un-guarded check would re-warn every subsequent pass,
    # reintroducing the per-pass nag the once-per-run base advisory prevents.
    audit_high_growth_rearmed = False
    # Build the read-only calibration rule once per audit operation. Every
    # pass evaluates the same frozen evidence, so history reads cannot change
    # the materiality decision mid-audit.
    sampler_checkpoint_path = _sampler_checkpoint_path(plan_path)
    sampler_plan_path = _checkpoint_plan_path(plan_path, repo_root)
    sampler_plan_slug = slug_from_filename(plan_path)
    assert sampler_plan_slug is not None
    sampler_input_hash = getattr(audit_input_snapshot, "fingerprint", "")
    try:
        from plan_tool.review_persistence import compute_plan_fingerprint

        sampler_plan_fingerprint = compute_plan_fingerprint(plan_path)
    except Exception as exc:  # noqa: BLE001 — a checkpoint remains best-effort
        sampler_plan_fingerprint = ""
        tool(
            f"plan-audit: failed to compute the sampler checkpoint's plan "
            f"fingerprint ({exc})",
            stream=out,
            level="warning",
        )
    try:
        sampler_audit_revision = (
            audit_input_snapshot.revision
            if audit_input_snapshot is not None
            else None
        )
    except Exception as exc:  # noqa: BLE001 — a checkpoint remains best-effort
        sampler_audit_revision = None
        tool(
            f"plan-audit: failed to capture audit-revision provenance for the "
            f"sampler checkpoint ({exc})",
            stream=out,
            level="warning",
        )
    try:
        from plan_tool.fingerprint import compute_code_fingerprint

        sampler_code_fingerprint: Optional[dict[str, str]] = (
            compute_code_fingerprint(plan, plan_path, repo_root)
            if audit_input_snapshot is not None
            else None
        )
    except Exception as exc:  # noqa: BLE001 — unavailable identity declines recovery
        sampler_code_fingerprint = None
        tool(
            "plan-audit: failed to compute the declared code fingerprint "
            f"({exc}); sampler checkpoints will not be resumable this run",
            stream=out,
            level="warning",
        )
    from plan_tool.backend import get_active_backend

    active_backend = get_active_backend()
    sampler_identity = _sampler_resume_identity(
        audit_input_fingerprint=sampler_input_hash,
        max_passes=max_passes,
        dry_rounds=dry_rounds,
        new_threshold=new_threshold,
        backend_name=active_backend.name,
        resolved_model=active_backend.resolved_model,
    )
    restored_sampler, resume_outcome = None, "absent"
    try:
        from plan_tool.review_persistence import load_sampler_checkpoint

        loaded_sampler = load_sampler_checkpoint(plan_path)
    except OSError:
        loaded_sampler = None
        resume_outcome = "malformed"
    if loaded_sampler is not None:
        if loaded_sampler.status == "valid" and loaded_sampler.review is not None:
            restored_sampler, resume_outcome = _restore_sampler_checkpoint_state(
                loaded_sampler.review,
                expected_identity=sampler_identity,
                expected_code_fingerprint=sampler_code_fingerprint,
            )
            if restored_sampler is not None and restored_sampler.passes >= cap:
                restored_sampler, resume_outcome = None, "malformed"
        elif loaded_sampler.status != "absent":
            resume_outcome = "malformed"

    if restored_sampler is None:
        demote_low_impact_medium = build_low_impact_demotion_lookup(repo_root)
        if resume_outcome == "identity-mismatch":
            tool(
                "plan-audit: sampler checkpoint identity mismatch — starting "
                "fresh at pass 1",
                stream=out,
            )
        elif resume_outcome == "malformed":
            tool(
                "plan-audit: sampler checkpoint malformed — starting fresh "
                "at pass 1",
                stream=out,
            )
        elif resume_outcome == "not-resumable":
            tool(
                "plan-audit: sampler checkpoint is not resumable — starting "
                "fresh at pass 1",
                stream=out,
            )
    else:
        by_id = restored_sampler.by_id
        materiality_by_id = restored_sampler.materiality_by_id
        observations_by_id = restored_sampler.observations_by_id
        consecutive_dry = restored_sampler.consecutive_dry
        passes = restored_sampler.passes
        conforming_pass_count = restored_sampler.conforming_pass_count
        failed_or_malformed_pass_count = (
            restored_sampler.failed_or_malformed_pass_count
        )
        stopped_on_dry = restored_sampler.stopped_on_dry
        early_stop_reason = restored_sampler.early_stop_reason
        dry_streak_grew = restored_sampler.dry_streak_grew
        dry_streak_unconfirmed_growth = restored_sampler.dry_streak_unconfirmed_growth
        dry_streak_low_yield = restored_sampler.dry_streak_low_yield
        terminal_reason = restored_sampler.terminal_reason
        advisory_invalid = restored_sampler.advisory_invalid
        demote_low_impact_medium = restored_sampler.low_impact_demotion_lookup
        if resumed_out is not None:
            resumed_out[:] = [True]
        tool(
            f"plan-audit: resuming sampler at pass {passes + 1}/{cap} with "
            f"{len(by_id)} carried finding(s)",
            stream=out,
        )
        if run_logger is not None:
            run_logger.checkpoint_hit(
                _SAMPLER_CHECKPOINT_NAME,
                sampler_input_hash,
                _checkpoint_payload_bytes(sampler_checkpoint_path),
            )

    # Frozen for the whole operation (see _SAMPLER_IDENTITY_FIELDS), so its
    # serialized form is the same on every pass — compute it once rather
    # than re-sorting and re-asdict-ing the cohort after every pass.
    sampler_low_impact_demotion_classes = _serialized_low_impact_demotion_classes(
        demote_low_impact_medium
    )

    def write_completed_sampler_boundary(
        *, lifecycle: str, terminal_state_reason: Optional[str] = None,
    ) -> Path:
        """Publish completed sampler state through the stable writer."""
        state = _sampler_checkpoint_state(
            lifecycle=lifecycle,
            identity=sampler_identity,
            passes=passes,
            consecutive_dry=consecutive_dry,
            materiality_by_id=materiality_by_id,
            observations_by_id=observations_by_id,
            conforming_pass_count=conforming_pass_count,
            failed_or_malformed_pass_count=failed_or_malformed_pass_count,
            stopped_on_dry=stopped_on_dry,
            dry_streak_grew=dry_streak_grew,
            dry_streak_unconfirmed_growth=dry_streak_unconfirmed_growth,
            dry_streak_low_yield=dry_streak_low_yield,
            advisory_invalid=advisory_invalid,
            early_stop_reason=early_stop_reason,
            terminal_reason=terminal_state_reason,
            low_impact_demotion_classes=sampler_low_impact_demotion_classes,
        )
        return _save_sampler_checkpoint(
            plan_slug=sampler_plan_slug,
            plan_path=sampler_plan_path,
            repo_root=repo_root,
            report_md=(
                "Conceptual-audit sampler checkpoint after "
                f"pass {passes}."
            ),
            recommendations=list(by_id.values()),
            sampler_state=state,
            plan_fingerprint=sampler_plan_fingerprint,
            code_fingerprint=sampler_code_fingerprint,
            checkpoint_audit_revision=sampler_audit_revision,
            plan=plan,
        )

    def log_checkpoint_save(path: Path) -> None:
        if run_logger is not None:
            run_logger.checkpoint_save(
                _SAMPLER_CHECKPOINT_NAME,
                sampler_input_hash,
                _checkpoint_payload_bytes(path),
            )

    def save_continuing_sampler_boundary() -> None:
        """Best-effort save for a pass that will render another prompt."""
        try:
            checkpoint = write_completed_sampler_boundary(lifecycle="in-progress")
        except (OSError, ValueError) as exc:
            tool(
                f"plan-audit: failed to save sampler checkpoint "
                f"{sampler_checkpoint_path} ({exc})",
                stream=out,
                level="warning",
            )
            return
        log_checkpoint_save(checkpoint)

    if invoker is not None:
        try:
            blocks: list[tuple[str, int]] = []
            base_prompt = render_plan_audit_prompt(
                plan,
                plan_path,
                repo_root=repo_root,
                collect_blocks=blocks,
                audit_input_snapshot=audit_input_snapshot,
            )
            if base_prompt is not None:
                total_bytes = len(base_prompt.encode("utf-8"))
                prompt_budget = maybe_warn_prompt_budget(
                    total_bytes,
                    context_window=active_context_window(),
                    blocks=blocks,
                    surface="plan audit",
                    stream=out,
                )
                record_prompt_budget(
                    repo_root,
                    plan_slug=slug_from_filename(plan_path),
                    phase="plan-audit",
                    total_bytes=total_bytes,
                    advisory=prompt_budget.level,
                    estimated_tokens=prompt_budget.estimated_tokens,
                    context_window=prompt_budget.context_window,
                    headroom_ratio=prompt_budget.headroom_ratio,
                    blocks=prompt_budget.blocks,
                )
                audit_budget_covered = True
                audit_base_bytes = total_bytes
                audit_base_warned_high = prompt_budget.level == "high"
        except DetailFormatError:
            raise
        except Exception:
            pass
    while passes < cap:
        passes += 1
        pass_invoker = invoker
        if reporter is not None and invoker is not None:
            pass_invoker = _make_reporting_invoker(
                invoker, reporter, passes, cap
            )
        # ``check_plan_audit`` returns ``[]`` both when a pass legitimately
        # finds nothing new and when the invoker raises / exits non-zero, so
        # wrap the invoker to make a failed pass observable. The flag lets
        # the stop logic keep an errored pass neutral instead of letting
        # two transient failures read as a dry-stop convergence.
        pass_errored = False
        if pass_invoker is not None:
            _inner_invoker = pass_invoker

            def _error_tracking_invoker(prompt: str) -> PlanAuditInvokerResult:
                nonlocal pass_errored
                # Conceptual-audit reporters carry no run log (unlike create's,
                # which tee their own start), so the start is written here,
                # once per call, beside the end's sink.
                if run_logger is not None:
                    run_logger.claude_call_start(
                        phase="plan_audit",
                        attempt=passes,
                        prompt_bytes=len(prompt.encode("utf-8")),
                        prompt_sha256=hash_prompt(prompt),
                    )
                try:
                    invocation = _inner_invoker(prompt)
                except Exception:
                    pass_errored = True
                    raise
                exit_code, _stdout, _failure_kind = (
                    _plan_audit_invocation_parts(invocation)
                )
                if exit_code != 0:
                    pass_errored = True
                return invocation

            pass_invoker = _error_tracking_invoker
        # Log each conceptual-audit pass as a ``plan_audit`` claude call so
        # a run log can price the up-front audit (its biggest Claude cost).
        # ``bind_shell_sink`` makes the shell invoker emit the paired
        # ``claude_call_end`` tagged with this phase/attempt.
        _audit_sink = (
            run_logger.bind_shell_sink(phase="plan_audit", attempt=passes)
            if run_logger is not None
            else contextlib.nullcontext()
        )
        carried = assemble_carried_findings(by_id.values())
        # Per-pass net, once per run (carried only grows), best-effort: the backstop's suppression
        # drops (1) when the base is not ``high`` now but base plus carried is, or (2) when the base
        # is ``high`` now and was never warned ``high`` (a window learned later was smaller than the
        # default). A base already warned ``high`` is skipped. See docs/ARCHITECTURE.md § "Prompt-budget window".
        pass_covered = audit_budget_covered
        if audit_budget_covered and not audit_high_growth_rearmed:
            try:
                # Re-measured against the window known now; a base never warned as ``high`` that reads
                # ``high`` now drops the suppression at once (docs/ARCHITECTURE.md § "Prompt-budget window").
                if estimate_prompt_budget(
                    audit_base_bytes, context_window=active_context_window()
                ).level == "high":
                    if not audit_base_warned_high:
                        pass_covered = False
                        audit_high_growth_rearmed = True
                else:
                    carried_bytes = len(
                        _format_carried_findings_block(carried).encode("utf-8")
                    )
                    pass_bytes = audit_base_bytes + carried_bytes
                    if estimate_prompt_budget(
                        pass_bytes, context_window=active_context_window()
                    ).level == "high":
                        pass_covered = False
                        audit_high_growth_rearmed = True
            except Exception:
                pass
        with suppress_prompt_budget_backstop(active=pass_covered), _audit_sink:
            sample_evidence: list[_AuditSampleEvidence] = []
            recs = check_plan_audit(
                plan,
                plan_path,
                repo_root=repo_root,
                invoker=pass_invoker,
                log_file=log_file,
                # Accumulated findings so far → the prompt's convergence-
                # guidance block, so this pass re-uses established ids for
                # re-found concepts and concentrates on the gaps earlier
                # passes have not yet covered.
                carried_findings=carried,
                audit_input_snapshot=audit_input_snapshot,
                _sample_evidence_out=sample_evidence,
            )
        pass_outcome = sample_evidence[-1].pass_outcome if sample_evidence else None
        if sample_evidence:
            if pass_errored or pass_outcome in {
                PASS_OUTCOME_FAILED_OR_MALFORMED,
                PASS_OUTCOME_TERMINAL_PLAN_QUOTA,
            }:
                failed_or_malformed_pass_count += 1
            elif pass_outcome == PASS_OUTCOME_CONFORMING:
                conforming_pass_count += 1
        if not sample_evidence or not sample_evidence[-1].advisory_valid:
            advisory_invalid = True
        else:
            for observation in sample_evidence[-1].observations:
                observations_by_id.setdefault(observation.finding_id, []).append(
                    (passes, observation.target_step_id)
                )
        new = 0
        new_recs_this_pass: list[Recommendation] = []
        for rec in recs:
            if rec.id not in by_id:
                by_id[rec.id] = rec
                new += 1
                new_recs_this_pass.append(rec)
        if (
            sample_evidence
            and sample_evidence[-1].pass_outcome
            == PASS_OUTCOME_TERMINAL_PLAN_QUOTA
        ):
            early_stop_reason = "plan-quota"
            terminal_reason = "plan-quota"
            tool(
                "plan-audit: sampling ended early after a terminal plan quota",
                stream=out,
                level="warning",
            )
        elif pass_errored:
            # An errored pass is neutral: it never advances the dry counter
            # and never triggers the dry-stop, so a flaky audit can't read as
            # convergence. It still consumed a slot against the cap, so the
            # loop falls through to the truncation log instead of "converged".
            tool(
                f"plan-audit: pass {passes}/{cap} errored — neutral, "
                f"not counted toward convergence",
                stream=out,
                level="warning",
            )
        elif pass_outcome == PASS_OUTCOME_SKIPPED and restored_sampler is not None:
            # Neutral like an errored pass on a resumed run — see
            # docs/how-to/recovery/audit.md's "A skipped pass never confirms
            # convergence on a resumed checkpoint".
            tool(
                f"plan-audit: pass {passes}/{cap} skipped — neutral, "
                f"not counted toward convergence",
                stream=out,
                level="warning",
            )
        else:
            if reporter is not None and cap > 1:
                tool(
                    f"plan-audit: pass {passes}/{cap} added {new} new "
                    f"finding(s) · {len(by_id)} unique so far",
                    stream=out,
                )
            # Material new findings this pass (see docs/how-to/pipeline/audit.md).
            material_new = []
            for rec in new_recs_this_pass:
                material = is_blocking_impact(
                    rec,
                    demote_low_impact_medium=demote_low_impact_medium,
                    classify_domain=classify_finding_domain,
                )
                materiality_by_id[rec.id] = material
                if material:
                    material_new.append(rec)
            count_ok = new >= max(1, new_threshold)
            # Productive = the count threshold is cleared AND the growth is
            # material. A below-threshold pass is non-productive regardless of
            # severity (unchanged pre-#125 behavior); a threshold-clearing pass
            # whose new findings are all advisory is *also* non-productive
            # (BACKLOG #125) no matter how many of them there are.
            productive = count_ok and bool(material_new)
            # The new #125 carve-out specifically: threshold cleared, but no
            # material finding among the new ones. Distinguished from a below-
            # threshold pass (which may still contain a material finding) so the
            # two-pass floor below applies only to genuinely severity-driven
            # stops, not to the pre-existing new_threshold mechanism.
            low_yield_reason = count_ok and not material_new
            if productive:
                consecutive_dry = 0
                dry_streak_grew = False
                dry_streak_unconfirmed_growth = False
                dry_streak_low_yield = False
            else:
                consecutive_dry += 1
                if new > 0:
                    dry_streak_grew = True
                    # Growth NOT covered by the #125 carve-out (a below-threshold
                    # pass, material or not) stays budget-limited on confirmation —
                    # only ``low_yield_reason`` growth is eligible for a clean
                    # low-yield stop. Gating this on ``material_new`` instead would
                    # silently let a below-threshold *advisory-only* pass slip
                    # through as a 1-pass "confirmed-low-yield" (the bug this
                    # fixes).
                    if not low_yield_reason:
                        dry_streak_unconfirmed_growth = True
                if low_yield_reason:
                    dry_streak_low_yield = True
                # A stop driven purely by the low-yield carve-out needs two
                # consecutive passes even at the default dry_rounds=1 (the
                # operator's "two repeated low-yield passes" proposal) — a
                # single advisory-only pass is suggestive, not confirmed. The
                # pre-existing dry/below-threshold mechanism is unaffected.
                required_streak = (
                    max(2, dry_rounds)
                    if dry_streak_low_yield
                    else max(1, dry_rounds)
                )
                if consecutive_dry >= required_streak:
                    stopped_on_dry = True
                    terminal_reason = "dry-streak"
        if run_logger is not None:
            # Observational only: a log-write failure must not cost the audit
            # the findings this pass already collected.
            try:
                run_logger.audit_pass_end(
                    pass_number=passes,
                    cap=cap,
                    outcome=(
                        "errored" if pass_errored else (pass_outcome or "unknown")
                    ),
                    new_ids=[rec.id for rec in new_recs_this_pass],
                    material_new_ids=[
                        rec.id
                        for rec in new_recs_this_pass
                        if materiality_by_id.get(rec.id)
                    ],
                    unique_so_far=len(by_id),
                )
            except Exception as exc:  # noqa: BLE001 — best-effort
                tool(
                    f"plan-audit: failed to log pass {passes} yield ({exc})",
                    stream=out,
                    level="warning",
                )
        if terminal_reason is None and passes >= cap:
            terminal_reason = "pass-cap"
        if terminal_reason is None:
            save_continuing_sampler_boundary()
            continue
        break
    try:
        checkpoint_exists = sampler_checkpoint_path.exists()
    except OSError as exc:
        # Unknown must not read as "no checkpoint" — see
        # docs/how-to/recovery/audit.md's "Terminal transition and cleanup".
        checkpoint_exists = True
        tool(
            f"plan-audit: failed to check for a sampler checkpoint at "
            f"{sampler_checkpoint_path} ({exc}); attempting the terminal "
            "transition anyway",
            stream=out,
            level="warning",
        )
    if checkpoint_exists:
        transition_published = False
        try:
            transition_checkpoint = write_completed_sampler_boundary(
                lifecycle="terminal-residue",
                terminal_state_reason=terminal_reason,
            )
        except (OSError, ValueError) as exc:
            # Resolve a write error from the durable artifact, not its exception.
            transition_published = _sampler_checkpoint_is_terminal_residue(plan_path)
            if transition_published:
                tool(
                    "plan-audit: terminal sampler checkpoint transition "
                    f"reported after publication ({exc})",
                    stream=out,
                    level="warning",
                )
                log_checkpoint_save(sampler_checkpoint_path)
            else:
                tool(
                    "plan-audit: failed to publish terminal sampler checkpoint "
                    f"transition ({exc}); preserving the prior boundary",
                    stream=out,
                    level="warning",
                )
        else:
            transition_published = True
            log_checkpoint_save(transition_checkpoint)
        if transition_published:
            try:
                _remove_sampler_checkpoint(sampler_checkpoint_path)
            except OSError as exc:
                tool(
                    f"plan-audit: failed to discard terminal sampler checkpoint "
                    f"{sampler_checkpoint_path} ({exc})",
                    stream=out,
                    level="warning",
                )
            else:
                if run_logger is not None:
                    run_logger.checkpoint_discard(
                        _SAMPLER_CHECKPOINT_NAME, "terminal"
                    )
    # Truncation is never silent (see docs/how-to/pipeline/audit.md for the full
    # budget-limited / confirmation_kind semantics, BACKLOG #125).
    budget_limited = (
        early_stop_reason is None
        and cap > 1
        and (not stopped_on_dry or dry_streak_unconfirmed_growth)
    )
    if budget_limited:
        tool(
            f"plan-audit: coverage budget-limited — stopped at the "
            f"{cap}-pass cap with convergence unconfirmed",
            stream=out,
            level="warning",
        )
    # BACKLOG #125 report semantics (docs/how-to/pipeline/audit.md): "confirmed-dry" vs
    # "confirmed-low-yield". Gated on ``stopped_on_dry`` (not just
    # ``not budget_limited``) because ``budget_limited`` is unconditionally
    # False for the ``cap == 1`` single-pass fallback — without this gate a
    # productive single pass that found genuine material findings would be
    # mislabeled "confirmed-dry" (it never went dry at all).
    confirmation_kind: Optional[str] = None
    if stopped_on_dry and not budget_limited and early_stop_reason is None:
        confirmation_kind = "confirmed-low-yield" if dry_streak_grew else "confirmed-dry"
        if confirmation_kind == "confirmed-low-yield":
            tool(
                f"plan-audit: converged low-yield — the final "
                f"{consecutive_dry}-pass streak kept discovering only "
                f"advisory (nit/info) findings, not zero-new; "
                f"{len(by_id)} finding(s) unioned over {passes} pass(es)",
                stream=out,
            )
    if passes > 1:
        tool(
            f"plan-audit: unioned {len(by_id)} finding(s) over "
            f"{passes} pass(es)",
            stream=out,
        )
    # Surface the budget-limited verdict to callers (BACKLOG #60c): a
    # budget-limited audit means "coverage unconfirmed" — the report must
    # record it so a `converged` reads as under-sampled, not fully validated,
    # rather than the signal vanishing with the transient stderr warning.
    if budget_report is not None:
        budget_report["budget_limited"] = budget_limited
        budget_report["passes_used"] = passes
        budget_report["cap"] = cap
        # Retained compatibility keys. Count-only pass-series guidance is
        # deliberately retired; the stored audit-shape advisory is the only
        # decision aid emitted by this audit path.
        budget_report["recommendation_kind"] = None
        budget_report["recommended_passes"] = None
        budget_report["recommendation_advice"] = None
        budget_report["confirmation_kind"] = confirmation_kind
        budget_report["conforming_pass_count"] = conforming_pass_count
        budget_report["failed_or_malformed_pass_count"] = failed_or_malformed_pass_count
        budget_report["early_stop_reason"] = early_stop_reason
    advisory: Optional[AuditShapeAdvisory] = None
    if not advisory_invalid and audit_input_snapshot is not None:
        # A changed prompt input means the saved advisory would describe no
        # coherent audit operation. Re-capture via the exact resolver path,
        # never through the generic saved-review fingerprint.
        if not audit_input_snapshot.matches_disk(plan_path, repo_root):
            advisory_invalid = True
        else:
            material_recs = [
                rec for rec in by_id.values() if materiality_by_id.get(rec.id, False)
            ]
            consensus_targets: dict[str, int] = {}
            for rec in material_recs:
                observed = observations_by_id.get(rec.id, [])
                target_ids = {target for _sample, target in observed}
                sample_ids = {
                    sample for sample, target in observed if target is not None
                }
                if (
                    len(observed) < 2
                    or len(sample_ids) < 2
                    or None in target_ids
                    or len(target_ids) != 1
                ):
                    advisory_invalid = True
                    break
                target = next(iter(target_ids))
                assert target is not None
                consensus_targets[rec.id] = target
            if not advisory_invalid:
                committed_step_ids = tuple(
                    step.id
                    for step in plan.steps
                    if step.scope is StepScope.COMMITTED
                )
                advisory = evaluate_arm_clustering(
                    declared_step_ids=committed_step_ids,
                    material_finding_ids=tuple(rec.id for rec in material_recs),
                    consensus_targets=consensus_targets,
                    source_plan_fingerprint=audit_input_snapshot.fingerprint,
                    material_finding_evidence=tuple(
                        AuditShapeFindingEvidence(
                            finding_id=rec.id,
                            anchor=rec.anchor,
                            source=rec.source,
                        )
                        for rec in material_recs
                    ),
                )
    if advisory_out is not None:
        advisory_out[:] = [advisory]
    return list(by_id.values())


def review_plan(
    plan_path: Path,
    *,
    repo_root: Path,
    plan_name: str,
    step_id: Optional[int] = None,
    invoker: Optional[Invoker] = shell_review_invoker,
    dry_run: bool = False,
    reporter: Optional[ProgressReporter] = None,
    no_heuristic: bool = False,
    allow_missing_parent: bool = False,
    extract_lessons: bool = False,
    strict_check: bool = False,
    equivalence_invoker: Optional[EquivalenceInvoker] = None,
    walk_will_run: bool = False,
) -> str:
    """Backwards-compatible wrapper around :func:`review_plan_full`.

    Existing callers (CLI's ``cmd_review``, tests) get a string back —
    the rendered markdown report or the dry-run prompt. New callers
    that need the structured recommendations should call
    :func:`review_plan_full` directly.
    """
    result = review_plan_full(
        plan_path,
        repo_root=repo_root,
        plan_name=plan_name,
        step_id=step_id,
        invoker=invoker,
        dry_run=dry_run,
        reporter=reporter,
        no_heuristic=no_heuristic,
        allow_missing_parent=allow_missing_parent,
        extract_lessons=extract_lessons,
        strict_check=strict_check,
        equivalence_invoker=equivalence_invoker,
        walk_will_run=walk_will_run,
    )
    return result.report


@spawn_cwd_from_repo_root
def review_plan_full(
    plan_path: Path,
    *,
    repo_root: Path,
    plan_name: str,
    step_id: Optional[int] = None,
    invoker: Optional[Invoker] = shell_review_invoker,
    dry_run: bool = False,
    reporter: Optional[ProgressReporter] = None,
    no_heuristic: bool = False,
    allow_missing_parent: bool = False,
    extract_lessons: bool = False,
    strict_check: bool = False,
    equivalence_invoker: Optional[EquivalenceInvoker] = None,
    walk_will_run: bool = False,
) -> ReviewResult:
    """End-to-end: parse, run deterministic checks, optionally call claude.

    Returns both the rendered markdown report and the structured
    ``recommendations`` list so the CLI can save the artifact without
    reparsing the report. Behaviorally identical to the prior
    ``review_plan`` (the ``str``-returning wrapper above) — same flags,
    same prompt rendering, same claude invocation.

    When ``dry_run=True``, ``report`` carries the rendered Claude prompt
    and ``recommendations`` is empty.

    When ``invoker=None`` the deterministic report is produced and the
    Claude section is populated with a short note. Tests typically use
    a fake ``Invoker`` to verify the Claude prompt contents.

    When ``no_heuristic=True`` the symbol-token "looks already done"
    scan is skipped entirely. File-existence, dep, and path-style
    checks still run; the Claude semantic review still fires (when an
    invoker is supplied).

    When ``allow_missing_parent=True``, MISSING_PARENT file-existence
    entries are promoted to NEW before the report and recommendations
    are assembled. This silences both the per-step MISSING_PARENT
    warning and the plan-wide path-style hint, while leaving every
    other check (NEW-on-DONE, deps, heuristic, claude) untouched. Use
    when a step legitimately creates files under a directory that
    doesn't exist yet.

    ``extract_lessons`` is **off by default** — the post-review lesson
    distillation is a second claude call, opted into with
    ``plan-tool reconcile-plan --lessons``.

    ``walk_will_run`` is forwarded to :func:`assemble_report` to slim the
    report when an interactive walk will present the findings (see that
    function). It is a no-op on ``dry_run=True``, which returns the
    rendered prompt before ``assemble_report`` is reached.
    """
    _reject_unmatched_plan_fence(plan_path)
    # Audit snapshots resolve the optional source-seed archive fallback before
    # this route can parse it into the scope contract or persist a report.
    from plan_tool.review_persistence import AuditInputError, AuditInputSnapshot

    try:
        AuditInputSnapshot.capture(plan_path, repo_root)
    except AuditInputError as exc:
        raise ReviewError(str(exc)) from exc
    plan = parse_plan(plan_path)
    if step_id is not None:
        try:
            plan.step_by_id(step_id)
        except KeyError as exc:
            raise ReviewError(str(exc)) from exc

    prompt = render_review_prompt(
        plan, repo_root, step_filter=step_id, plan_path=plan_path
    )

    if dry_run:
        return ReviewResult(report=prompt, recommendations=[], dry_run=True)

    # Correctness checks first — these gate structural correctness
    # (paths, deps, heuristic-already-done). Completeness checks below
    # ride on top and surface authoring gaps. Order is load-bearing for
    # report rendering (see ``assemble_report`` and
    # ``extract_recommendations``).
    file_checks = check_file_existence(plan, repo_root)
    if allow_missing_parent:
        file_checks = _promote_missing_parents(file_checks)
    hits = [] if no_heuristic else heuristic_already_done(plan, repo_root)
    deps = validate_deps(plan)
    path_style_hint = detect_path_style_mismatch(file_checks, repo_root)

    # Completeness checks (deterministic; no claude). Run after
    # correctness so the report can render correctness findings ahead of
    # completeness ones — matches the user-facing convention that
    # structural blockers come before authoring gaps.
    body_completeness_issues = check_body_completeness(plan_path)
    detail_coverage_issues = check_detail_coverage(plan, plan_path, repo_root)
    detail_body_issues = check_detail_body_completeness(
        plan, repo_root, plan_path=plan_path
    )
    files_coherence_issues = check_files_coherence(
        plan, repo_root, plan_path=plan_path
    )
    lessons_coverage_issues = check_lessons_coverage(plan, repo_root)
    input_contract_issues = check_input_contract_references(
        plan, plan_path, repo_root, step_filter=step_id
    )

    # Deterministic pairwise granularity signals (full reconcile lane only).
    # Body-local import keeps the granularity → review edge one-way: granularity
    # imports review at module load, so review must not import it at the top.
    # ``stage="completeness"`` is the no-Claude structural mode; no invoker is
    # passed, so this spends no Claude.
    granularity_recs: list[Recommendation] = []
    if step_id is None:
        from plan_tool.granularity import GranularityEvidence, assess_granularity

        granularity_recs = assess_granularity(
            plan, stage="completeness", evidence=GranularityEvidence()
        )

    claude_review: Optional[str] = None
    claude_note: Optional[str] = None
    claude_stdout_for_recs: Optional[str] = None
    if invoker is None:
        claude_note = "Claude review skipped (no invoker supplied)."
    else:
        # Default to stderr reporting; tests inject NullReporter to keep
        # captured stderr deterministic. Only the claude call gets a
        # progress line — the deterministic local checks above are too
        # fast to be worth reporting on.
        if reporter is None:
            reporter = StderrReporter()
        handle = reporter.start_step(1, 1, "Claude semantic review")
        start = time.monotonic()
        exit_code, stdout = invoker(prompt)
        elapsed = time.monotonic() - start
        # Lazy import: review is imported by backend-adjacent modules;
        # resolving the name at call time keeps the edge one-way and
        # honors test patches.
        from plan_tool.backend import get_active_backend

        _backend_name = get_active_backend().name
        if exit_code == 127:
            handle.fail(elapsed, f"{_backend_name} executable not found")
            claude_note = (
                f"Backend review skipped (`{_backend_name}` executable "
                "not found)."
            )
        elif exit_code != 0:
            handle.fail(elapsed, f"{_backend_name} exited with code {exit_code}")
            claude_note = (
                f"Claude review skipped (invoker exited with code {exit_code})."
            )
        elif stdout.strip():
            handle.complete(elapsed, len(stdout.encode("utf-8")))
            claude_review = stdout
            claude_stdout_for_recs = stdout
        else:
            handle.fail(elapsed, "claude returned an empty response")

    # Recommendations are computed before the report so the report's
    # severity banner can tally them. Both are pure functions over the same
    # primitives, so the order swap is behavior-preserving.
    recommendations = extract_recommendations(
        plan,
        plan_name,
        repo_root=repo_root,
        file_checks=file_checks,
        heuristic_hits=hits,
        dep_issues=deps,
        path_style_hint=path_style_hint,
        claude_stdout=claude_stdout_for_recs,
        step_filter=step_id,
        body_completeness=body_completeness_issues,
        detail_coverage=detail_coverage_issues,
        detail_body=detail_body_issues,
        files_coherence=files_coherence_issues,
        lessons_coverage=lessons_coverage_issues,
        input_contract_references=input_contract_issues,
        reconcile_lane=True,
        granularity_recommendations=granularity_recs,
        plan_path=plan_path,
    )
    report = assemble_report(
        plan,
        plan_name,
        repo_root=repo_root,
        file_checks=file_checks,
        heuristic_hits=hits,
        dep_issues=deps,
        claude_review=claude_review,
        claude_note=claude_note,
        step_filter=step_id,
        path_style_hint=path_style_hint,
        body_completeness=body_completeness_issues,
        detail_coverage=detail_coverage_issues,
        detail_body=detail_body_issues,
        files_coherence=files_coherence_issues,
        lessons_coverage=lessons_coverage_issues,
        recommendations=recommendations,
        walk_will_run=walk_will_run,
    )

    # Lesson capture is a second, separate claude call. Skipped when:
    #   - extract_lessons=False (the default; --lessons opts in)
    #   - no invoker (tests / claude-not-on-PATH)
    #   - the review didn't actually run claude (claude_stdout_for_recs
    #     is None — extraction has no findings to generalize from)
    #   - recommendations is empty (nothing to distill)
    # Failures here are swallowed: lesson capture is best-effort and
    # must never break a review.
    if (
        extract_lessons
        and invoker is not None
        and claude_stdout_for_recs is not None
        and recommendations
    ):
        try:
            n_general, n_project = extract_and_append_review_lessons(
                plan_name=plan_name,
                plan_title=plan.title,
                report_md=report,
                recommendations=recommendations,
                invoker=invoker,
                repo_root=repo_root,
                reporter=reporter,
                strict_check=strict_check,
                equivalence_invoker=equivalence_invoker,
            )
            if (n_general + n_project) > 0:
                # Surface on stderr so users can see a lesson actually
                # got captured without re-reading the file. Indented to
                # nest visually under the surrounding step header (same
                # convention as the detail-quality status lines).
                print(
                    f"        captured {n_general} general + "
                    f"{n_project} project lesson(s) from review",
                    file=sys.stderr,
                )
        except Exception as exc:  # noqa: BLE001 — best-effort
            # Errors keep the ``plan-tool:`` prefix so they stand out
            # against the indented informational lines.
            tool(
                f"lesson extraction failed ({exc}); review "
                "report is unaffected",
                stream=sys.stderr,
            )

    return ReviewResult(report=report, recommendations=recommendations)


def extract_and_append_review_lessons(
    *,
    plan_name: str,
    plan_title: str,
    report_md: str,
    recommendations: list[Recommendation],
    invoker: Invoker,
    repo_root: Path,
    reporter: Optional[ProgressReporter] = None,
    strict_check: bool = False,
    equivalence_invoker: Optional[EquivalenceInvoker] = None,
) -> AppendLessonsResult:
    """Run the extract-lessons-review prompt and append distilled lessons.

    Returns an :class:`AppendLessonsResult` (which destructures to
    ``(n_general_added, n_project_added)``) after dedupe. A result of
    ``(0, 0)`` is a normal outcome — either claude found nothing new to
    capture, or every candidate lesson collided with an existing entry.
    ``strict_check`` / ``equivalence_invoker`` are forwarded to
    :func:`append_lessons`; refused entries surface on the result's
    ``*_dropped`` fields. Failures bubble up so the caller can decide
    whether to surface them.
    """
    prompt = _render_extract_lessons_prompt(
        plan_name=plan_name,
        plan_title=plan_title,
        report_md=report_md,
        recommendations=recommendations,
        repo_root=repo_root,
    )
    if reporter is None:
        reporter = StderrReporter()
    handle = reporter.start_step(1, 1, "Distilling lessons from review")
    start = time.monotonic()
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
    return append_lessons(
        repo_root,
        general=general,
        project=project,
        source=f"review:{plan_name}",
        strict_check=strict_check,
        equivalence_invoker=equivalence_invoker,
    )


def _render_extract_lessons_prompt(
    *,
    plan_name: str,
    plan_title: str,
    report_md: str,
    recommendations: list[Recommendation],
    repo_root: Path,
) -> str:
    """Render ``prompts/extract-lessons-review.md`` with the review's findings."""
    template_path = prompts_dir() / "extract-lessons-review.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    lessons_block = render_lessons_block(load_lessons(repo_root))
    findings_lines: list[str] = []
    for rec in recommendations:
        sev = rec.severity.upper()
        step = f" step={rec.step_id}" if rec.step_id is not None else ""
        findings_lines.append(
            f"- [{sev}] [{rec.source}{step}] [{confidence_label(rec.confidence)}] "
            f"**{rec.title.strip()}** — "
            f"{indent_bullet_body(rec.body.strip())}"
        )
    findings_block = "\n".join(findings_lines) if findings_lines else (
        "_(no structured recommendations — see report body below)_\n\n"
        + report_md
    )
    return template.safe_substitute(
        plan_title=plan_title,
        plan_slug=plan_name,
        lessons_block=lessons_block,
        findings_block=findings_block,
    )
