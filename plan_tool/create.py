"""Interactive authoring wizard for new plans.

`create_plan` prompts for metadata + at least one step, writes a new markdown
file, and registers its repo-relative path in `structured_plans.json`. `input_fn`
and `claude_invoker` are injectable so tests never block on stdin or shell out.

Why "at least one step" when the detail file says "empty steps initially":
`Plan.steps` has `min_length=1` in the schema. An empty-steps plan cannot
validate, so the wizard loops until it has collected one, then asks "Add
another?".

Why write-stub-then-`write_plan` instead of serializing frontmatter from
scratch: `write_plan` is the canonical serializer used by every other edit to a
plan file. Routing the initial write through the same code path means new
plans come out formatted identically to plans that have been round-tripped.
"""

from __future__ import annotations

import json
import hashlib
import re
import select
import shutil
import sys
import time
import uuid
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from string import Template
from typing import Any, Callable, Literal, Optional, Protocol, Sequence, TypeVar

from plan_tool.pathutil import display_path, is_within
from plan_tool.roadmap_artifacts import (
    RoadmapArtifactError,
    ResearchDisclosure,
    parse_components_artifact,
    parse_constraints_artifact,
)
from plan_tool.roadmap_seed_manifest import (
    NoPublishedRoadmapVersionError,
    no_published_version_message,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    RoadmapVersionError,
    load_accepted_version,
)
from plan_tool.roadmap_seed_state import TrackedSeedLocation
from plan_tool.project_profile import (
    project_profile_context,
    render_project_context_block,
)
from plan_tool.backend import spawn_cwd_from_repo_root
from plan_tool.foundational_logic import (
    logged_invoke,
    merge_sweep_into_steps,
    run_foundational_logic_sweep,
    step_has_foundational_footprint,
)
from plan_tool.scenario_capture import (
    CATEGORY_FAILURE,
    CATEGORY_FOUNDATIONAL,
    CATEGORY_MIXED_STEP,
    PROMPT_MODE_EXPERIMENT,
    arm_from_split,
    capture_scenario,
    categorize_scenario,
)
from plan_tool.renderer import prompts_dir
# Plan-body H2 recognition and the author-supplied guardrail headings live in
# the ``plan_tool.scope_fence`` leaf (shared with ``detail``'s fence renderer);
# re-imported here so every historical ``plan_tool.create`` import path — in
# particular ``reprocess``'s ``_H2_HEADING_RE`` — keeps returning the same
# objects. ``_strip_frontmatter`` is private but reused rather than mirrored:
# a second copy could drift from the shadowing rule its docstring records.
from plan_tool.scope_fence import (
    FencedCodeScan,
    _fenced_code_spans,
    _is_placeholder_section,
    collapse_intent_to_one_line,
    GUARDRAIL_BODY_SECTIONS,
    _H2_HEADING_RE,
    _strip_frontmatter,
    extract_h2_section_occurrences,
    extract_h2_sections,
    is_placeholder_intent,
)
from plan_tool.runner_detect import qualify_uv_pytest_command
from plan_tool.shell import (
    claude_invoke,
    shell_concept_invoker,
    suppress_prompt_budget_backstop,
)
from plan_tool.style import BOLD, BOLD_RED, DIM, color_enabled, paint, tool, warn

from pydantic import ValidationError as PydanticValidationError

from plan_tool.checkpoint import (
    Checkpoint,
    checkpoint_dir,
    checkpoint_path,
    compute_input_hash,
    discard_checkpoint,
    load_if_valid,
    save_checkpoint,
)
from plan_tool.fileio import durable_write_text
from plan_tool.convergence import (
    ConvergenceState,
    IterativeBudget,
    finding_set_delta,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.lessons import LessonsBundle, load_lessons, render_lessons_block
from plan_tool.distill_thresholds import (
    DISTILL_ADVISE_ABOVE_BYTES,
    DISTILL_SKIP_BELOW_BYTES,
)
from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.locator import default_manifest_path
from plan_tool.parser import (
    BodySection,
    ParseError,
    ValidationError,
    parse_body_sections,
    parse_plan,
    write_plan,
)
from plan_tool.response_contract import (
    JSON_ROOT_ARRAY,
    JsonResponseContract,
    coerce_response_id,
)
from plan_tool.concept_bootstrap import (
    bootstrap_concepts,
    carry_forward_decisions,
    rederive_concepts,
)
from plan_tool.concept_review import review_concept_scope
from plan_tool.concept_sync import render_scope_decisions, synchronize_concepts
from plan_tool.concept_tree import (
    RECORD_KIND_DECISION,
    ConceptNode,
    ConceptTree,
    InvalidConceptTreeError,
    StaleConceptTreeError,
    concepts_path,
    load_concepts,
    save_concepts,
)
from plan_tool.run_log import hash_prompt
from plan_tool.progress import ProgressReporter, StderrReporter
from plan_tool.prompt_excerpt import build_prompt_excerpt
from plan_tool.canonical import (
    CanonicalProvenance,
    extract_canonical_steps,
    has_canonical_steps_marker,
    read_canonical_provenance,
)
from plan_tool.fileio import atomic_write_text
from plan_tool.fetch import (
    FetchedDoc,
    docs_from_json,
    docs_to_json,
    fetch_reference_docs,
    render_reference_docs_block,
)
from plan_tool.intent_proposal import (
    apply_intent_drafts,
    propose_intents,
    review_intent_drafts,
)
from plan_tool.launcher import apply_finding, revert_apply_if_parse_broken
from plan_tool.review import (
    FileCheck,
    FileExistence,
    StepFileCheck,
    check_file_existence,
    collect_deterministic_findings,
    detect_path_style_mismatch,
    is_usable_intent,
    confidence_label,
    format_recommendation_for_apply,
)
from plan_tool.schema import (
    ChangeType,
    Complexity,
    Plan,
    PlanStatus,
    Priority,
    RiskProfile,
    Step,
    StepStatus,
)
from plan_tool.granularity import (
    DETERMINISTIC_SPLIT_PREDICATE_KEYS,
    GRANULARITY_MERGE_SOURCE,
    GRANULARITY_SPLIT_SOURCE,
    GranularityEvidence,
    assess_granularity,
    split_predicate_key,
)
from plan_tool.prompt_budget import maybe_warn_prompt_budget
from plan_tool.context_window import active_context_window
from plan_tool.telemetry import (
    CREATE_ACTION_ACCEPT,
    CREATE_ACTION_OVERRIDE,
    CREATE_ACTION_SPLIT_APPLIED,
    CREATE_ACTION_SPLIT_ERROR,
    CREATE_ACTION_SPLIT_INVALID,
    CREATE_ACTION_SPLIT_REQUESTED,
    CREATE_ACTION_SPLIT_UNUSABLE,
    CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
    CREATE_ACTION_UNCLASSIFIED_CLASSIFIED,
    CREATE_MODE_CHECKPOINT,
    CREATE_MODE_INTERACTIVE,
    CREATE_MODE_NON_TTY,
    CREATE_MODE_YES,
    record_create_granularity_assessment,
    record_create_step_outcome,
    record_prompt_budget,
)


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
PRIORITY_PREFIX: dict[Priority, int] = {
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}
DEFAULT_OUTPUT_DIR = Path("docs") / "implementation-plans"

# Body skeleton seeded into newly-created plans. Mirrors the H2 section
# structure of the existing in-repo plans (5-correctness-checks,
# 6-heuristic-tightening, etc.) so authors don't have to remember the
# convention. Each section gets a `_(TODO)_` placeholder; the author
# replaces them. Pure prose — no claude involvement here.
PLAN_BODY_SECTIONS = (
    "Overview",
    "Problem statement",
    "Architecture",
    "References",
    "Steps",
    "Out of scope",
    "Risks",
    "Testing",
    "Acceptance criteria",
    "Deferred",
)

# Recommended content shape per section. Consumed by
# ``review._body_completeness_recommendation`` so a placeholder finding
# carries concrete guidance about what content should fill the section,
# rather than just flagging "this is empty." Without a shape, claude's
# ``apply_finding`` step reasonably refuses placeholder findings as
# "too vague to act on without guessing content" (observed during the
# bug #24 verification run).
#
# Keep these shapes tight (one sentence each). The goal is to give
# claude a target, not to dictate prose.
PLAN_BODY_SECTION_SHAPES: dict[str, str] = {
    "Overview": (
        "2-4 sentence summary of what this plan adds: what the feature "
        "does, why it exists, and the key constraints "
        "(defaults, exit codes, integration points) a reader needs "
        "before diving into the steps. Use plain, common words a "
        "reader grasps the first time through -- keep exact "
        "identifiers, but skip fancy vocabulary."
    ),
    "Problem statement": (
        "What's broken or missing today, why fixing it matters, and "
        "the user-visible symptom that motivates this work, in plain "
        "words with the symptom first. Cite "
        "existing code/spec by symbolic anchor where relevant."
    ),
    "Architecture": (
        "Design choices made by this plan: components introduced, how "
        "they interact, where they sit in the existing dependency "
        "graph, and the major design trade-offs (a short paragraph "
        "per non-obvious choice, opening with the choice itself, after any "
        "seed/code conflict callout)."
    ),
    "References": (
        "Bulleted list of authoritative sources -- spec docs, RFCs, "
        "vendor APIs, related plans -- each with a one-line note on "
        "why it matters here. Falls back to `_(TODO)_` when the body "
        "is otherwise empty."
    ),
    "Steps": (
        "Pointer to the `steps:` block in the frontmatter. The "
        "machine-readable list lives there; restating it in prose is "
        "the most common drift source."
    ),
    "Out of scope": (
        "Bulleted exclusions with a one-line rationale each. Captures "
        "the work this plan deliberately doesn't tackle, so future "
        "reviewers don't re-litigate the boundary."
    ),
    "Risks": (
        "Bulleted failure modes, each with: the failure shape, the "
        "severity, the mitigation if any, and any unresolved gap. "
        "Aim for honest exposure (e.g. 'apply_finding can wander out "
        "of scope; guarded by scope_guard'), not aspirational risk-"
        "free framing."
    ),
    "Testing": (
        "How the plan's behavior is verified. Follow the project's "
        "unit-first convention: default to unit tests that exercise "
        "one function or class in isolation; add INTEGRATION tests "
        "ONLY for cross-module wiring (driving CLI entry points, "
        "calling orchestrators, exercising end-to-end pipelines where "
        "a unit test on any single piece would miss the bug). Use "
        "whatever marker / file split the project already uses to "
        "distinguish the two tiers (e.g. `@pytest.mark.integration` "
        "for pytest projects, `*.integration.test.ts` for TS/JS "
        "projects, build tags for Go) -- if `TESTING.md` exists at "
        "the repo root, follow its convention. For each test file: "
        "cite the path; for each test case: cite the class / "
        "function / describe-block name. List existing suites that "
        "must still pass. If this plan touches a conceptual area "
        "covered by the project's integration tier, name the "
        "specific integration tests the iterator should run when "
        "modifying the affected source files. NOTE: the rendered "
        "section ends with a deterministic test-strategy list derived "
        "from each step's `change_type`, one line per change type naming "
        "its steps (code steps "
        "→ tests covering the changed behavior, green before completion; "
        "non-code → artifact-appropriate verification); give "
        "cross-cutting test guidance here and do NOT re-list per-step "
        "test strategy — the enumeration owns that."
    ),
    "Acceptance criteria": (
        "Bulleted verifiable invariants -- one per criterion. Each "
        "bullet should be testable from outside the codebase (e.g. "
        "'`plan-tool foo --bar` exits 0 when X'), citing specific "
        "files/functions/tests where applicable. NOTE: this section "
        "feeds `plan-tool completeness`'s conceptual audit -- vague or "
        "unfalsifiable bullets ('is reasonable', 'works well') get "
        "flagged because an untestable criterion makes the plan's "
        "completeness unanswerable. Write criteria a test could prove "
        "or disprove."
    ),
    "Deferred": (
        "Bulleted items deliberately dropped or postponed during "
        "implementation, each with a one-line note explaining why "
        "(too large, blocked, separate concern). Distinct from "
        "`## Out of scope`: deferred items might come back; "
        "out-of-scope items are permanent exclusions."
    ),
}

OPTIONAL_PLAN_BODY_SECTION_SHAPES: dict[str, str] = {
    "Input": (
        "Conditional section for work that consumes an existing contract: "
        "name the data structure, persisted schema, API surface, saved "
        "audit, output format, or dependency-step output this plan reads; "
        "cite the fields or code locations relied on; and state any limits "
        "on verifying that contract. Omit this section entirely when the "
        "plan does not consume an existing contract."
    ),
    "Scope guardrails": (
        "Conditional, source-backed boundary section. Preserve the supplied "
        "body verbatim when the seed includes this heading; do not invent or "
        "revise scope decisions."
    ),
    "Audit guardrails": (
        "Conditional, source-backed audit boundary section. Preserve the "
        "supplied body verbatim when the seed includes this heading; do not "
        "invent or revise audit decisions."
    ),
    "Expected placement": (
        "Conditional, source-backed placement section. Preserve the supplied "
        "body verbatim when the seed includes this heading; do not invent or "
        "revise placement decisions."
    ),
    "Stack": (
        "Conditional, source-backed hosting and store section. Preserve the "
        "supplied body verbatim when the seed includes this heading; do not "
        "invent or revise stack decisions."
    ),
}

_OPTIONAL_PLAN_BODY_SECTIONS: tuple[str, ...] = tuple(
    OPTIONAL_PLAN_BODY_SECTION_SHAPES
)

# Per-section synthesis policy. "Derive-from-intent" sections follow
# logically from any stated goal: a seed that says *what* to build is itself
# the source for its Overview, the *why* is its Problem statement, and the
# design that goal implies is its Architecture -- so the distill/synthesis
# passes should author them rather than null out when the seed lacks the
# literal heading. Restating intent is not inventing facts. Every other
# canonical section stays evidence-only: emit only what the seed (or fetched
# docs) supports, null otherwise -- a fabricated risk / test / criterion /
# scope boundary / deferral introduces a false commitment the downstream
# conceptual audit rightly flags. Consumed by `_render_section_shapes_block`,
# which tags each catalog bullet so both prompts steer by one source of truth.
_DERIVE_FROM_INTENT_SECTIONS: frozenset[str] = frozenset(
    {"Overview", "Problem statement", "Architecture"}
)

# One-line test-discipline phrasing per `change_type`, keyed off the enum so
# the parenthetical label and the strategy text track the schema. Consumed by
# :func:`_render_testing_strategy`, which appends a per-change-type list below
# the rendered ``## Testing`` body. NOTE: steps 5 (`detail.py`) and 6
# (`launcher.py`) carry parallel per-type wording for the detail/run prompts;
# this copy is intentionally local — this step's `depends_on` (2, 3) forbids an
# import edge to those siblings. Consolidating the three is routed to Deferred.
_TESTING_STRATEGY_BY_CHANGE_TYPE: dict[ChangeType, str] = {
    ChangeType.REFACTOR: (
        "tests covering the behavior a step changes; green before completion."
    ),
    ChangeType.FEATURE: (
        "tests covering the behavior a step changes; green before completion."
    ),
    ChangeType.NON_CODE: (
        "verification appropriate to the artifacts rather than unit tests."
    ),
}

# Checkpoint names for the two claude round-trips made inside ``create_plan``.
# The filenames land under ``.plan-tool/checkpoints/<slug>/`` via
# ``checkpoint_path``; the constants are referenced by the propose helpers
# and by the discard loop at the tail of ``create_plan``.
_INITIAL_STEPS_CHECKPOINT_NAME = "create-initial-steps"
_REFERENCES_CHECKPOINT_NAME = "create-references"
_BODY_SECTIONS_CHECKPOINT_NAME = "create-body-sections"
_ROADMAP_NO_SOURCE_REFERENCES_BODY = (
    "No external references were returned for the selected roadmap products; "
    "publication proceeds under their recorded operator descriptions."
)
# First-pass "distill" round-trip: reorganizes the raw seed into canonical
# body sections (single-plan) or proposes a multi-plan split. Runs once,
# before the other three, and feeds them its cleaned output.
_DISTILL_SEED_CHECKPOINT_NAME = "create-distill-seed"
# Direct assessment and preparation deliberately keep distinct cache files.
# Their result grammars overlap on ``split`` but are not interchangeable.
_DIRECT_ASSESSMENT_CHECKPOINT_NAME = "create-direct-assessment"
_PREPARATION_CACHE_DISCRIMINATOR = "preparation"
_DISTILL_RESULT_CONTRACT_REVISION = "2"
_DIRECT_ASSESSMENT_CONTRACT_REVISION = "1"
# Seed-only risk classification is deliberately independent from distillation:
# it is keyed to the source evidence and the exact target it could publish.
_RISK_PROFILE_CHECKPOINT_NAME = "create-risk-profile"
_RISK_PROFILE_PHASE = "propose_risk_profile"
_RISK_PROFILE_CLASSIFIER_POLICY_REVISION = "1"
# The classifier proposal remains private advice. This checkpoint records the
# separate operator-owned declaration that may safely cross the write boundary.
_RISK_DECLARATION_CHECKPOINT_NAME = "create-risk-declaration"
# Reference-content fetch: turns the URLs from the references round-trip
# into extracted page text that grounds the body-sections synthesis. Runs
# once (round 0 only), between references and synthesis. Payload is a
# JSON-serialized list of ``FetchedDoc`` (see ``plan_tool.fetch``).
_REFERENCE_DOCS_CHECKPOINT_NAME = "create-reference-docs"
# Per-step change-type review: stores the operator-reviewed step list after
# the create wizard's decision gate (confirm / override / split). Unlike the
# other create checkpoints it caches a *post*-review structural result (the
# split path inserts steps and rewires the graph), so it can't ride the raw
# initial-steps reparse — it gets its own checkpoint keyed on the pre-review
# proposal. Payload is a JSON-serialized list of ``Step.model_dump(...)``.
_STEP_REVIEW_CHECKPOINT_NAME = "create-step-review"
# Intent offer: stores the operator-reviewed plan *and* step ``intent`` values
# after the create wizard's intent decision gate (accept / edit / decline each
# drafted line). Runs last of the two gates, so it is keyed on the final step
# list plus the plan-level intent the seed mapped. Unlike the step-review
# checkpoint its payload is a JSON object — the reviewed plan intent beside the
# same ``Step.model_dump(...)`` list — because the pass reviews both altitudes.
_INTENT_REVIEW_CHECKPOINT_NAME = "create-intent"

# Run-log phase for the intent offer. Deliberately the phase
# ``intent_proposal.propose_intents`` installs its call-end sink under, so the
# call event nests inside the phase that made it (as ``propose_references``
# does).
_INTENT_PHASE_NAME = "propose_intents"


# Canonical keys the body-sections synthesis round-trip is responsible for.
# Derived once from :data:`PLAN_BODY_SECTIONS` by filtering out ``Steps`` (a
# pointer to the frontmatter list) and ``References`` (its own web-research
# round-trip). Adding a new entry to ``PLAN_BODY_SECTIONS`` automatically
# expands this tuple; the synthesis prompt's literal key list in
# ``prompts/synthesize-body.md`` is the only other place the names appear
# and step 1's acceptance criterion pins the two in sync.
_BODY_SECTIONS_CANONICAL_KEYS: tuple[str, ...] = tuple(
    s for s in PLAN_BODY_SECTIONS if s not in ("Steps", "References")
)

ARCHIVE_DIRNAME = "archive"


# Anything with the methods ``plan_tool.run_log.RunLogWriter`` exposes
# — ``phase_start`` / ``phase_end`` / ``checkpoint_*`` /
# ``install_call_end_sink`` / ``uninstall_call_end_sink``. The shape is
# structural (``object`` rather than the concrete class) so tests can
# pass recording fakes without subclassing the real writer or pulling
# its filesystem dependencies into the test setup.
RunLoggerLike = object
REPLACED_SUFFIX = ".replaced"

InputFn = Callable[[str], str]
ClaudeInvoker = Callable[[str], str]  # returns stdout

# Prompt-default passthrough type for ``_eof_default`` (str / bool / list).
_T = TypeVar("_T")


class CreateError(Exception):
    """Wizard-level problems: bad slug, bad manifest, plan path outside repo."""

    def __init__(
        self,
        message: str,
        *,
        artifact: Optional["_CreatedArtifact"] = None,
    ) -> None:
        super().__init__(message)
        self.artifact = artifact


class FileBackedSourceRoute(str, Enum):
    """Terminal routes available to later file-backed intake dispatch."""

    DIRECT = "direct"
    NORMALIZED = "normalized"
    SPLIT = "split"
    REFUSED = "refused"


@dataclass(frozen=True)
class FileBackedRouteLifecycle:
    """One route-owned disposition for checkpoints and CLI artifacts."""

    archive_source_chain: bool
    materialize_normalized_artifact: bool
    checkpoint_action: Literal["retain", "discard_all", "discard_route"]


def file_backed_route_lifecycle(
    route: Optional[FileBackedSourceRoute],
    *,
    source_identity: Optional[Path],
    finalization_complete: bool,
    normalized_payload: Optional[str],
) -> FileBackedRouteLifecycle:
    """Select file-backed retention from the explicit route, never payload shape."""
    clean_publication = finalization_complete and source_identity is not None
    if route is None:
        # Inline creates retain their established checkpoint lifecycle.
        return FileBackedRouteLifecycle(
            False,
            False,
            "discard_all" if finalization_complete else "retain",
        )
    if route is FileBackedSourceRoute.DIRECT:
        return FileBackedRouteLifecycle(
            archive_source_chain=clean_publication,
            materialize_normalized_artifact=False,
            checkpoint_action=("discard_all" if finalization_complete else "retain"),
    )
    if route is FileBackedSourceRoute.NORMALIZED:
        normalized_artifact_ready = (
            clean_publication and normalized_payload is not None
        )
        return FileBackedRouteLifecycle(
            archive_source_chain=normalized_artifact_ready,
            materialize_normalized_artifact=normalized_artifact_ready,
            checkpoint_action=("discard_all" if finalization_complete else "retain"),
        )
    if route is FileBackedSourceRoute.SPLIT:
        return FileBackedRouteLifecycle(False, False, "retain")
    if route is FileBackedSourceRoute.REFUSED:
        return FileBackedRouteLifecycle(False, False, "discard_route")
    raise AssertionError(f"unhandled file-backed route: {route}")


@dataclass(frozen=True)
class FileBackedSourceIntake:
    """Deterministic facts read from one selected file-backed source."""

    references_ready: bool
    direct_ready: bool
    strict_steps: Optional[list[Step]]

    @property
    def needs_preparation(self) -> bool:
        """Whether the body shape needs a later preparation route."""
        return not self.direct_ready


def select_file_backed_source(
    seed_body: Optional[str], from_description: Optional[str]
) -> str:
    """Select provenance prose without treating an empty body as absent."""
    if seed_body is not None:
        return seed_body
    return from_description if from_description is not None else ""


def classify_file_backed_source(
    source_text: str, *, source: Path | str = "--from-existing seed"
) -> FileBackedSourceIntake:
    """Classify source evidence, body readiness, and strict steps once."""
    text = _strip_frontmatter(source_text)
    scan = _fenced_code_spans(text)
    reject_unmatched_create_fence(source_text, source, fence_scan=scan)
    occurrences = extract_h2_section_occurrences(
        text, strip_fenced_code=True, fenced_spans=scan.spans
    )
    references = occurrences.get("references", [])
    if (
        len(references) != 1
        or not references[0]
        or _is_placeholder_section(references[0])
    ):
        raise CreateError(
            "--from-existing seed requires exactly one non-placeholder "
            "`## References` section before authoring. Add the developer/API "
            "references or source evidence the plan relies on and retry; no "
            "authoring model was invoked."
        )

    direct_ready = all(
        len(section_occurrences := occurrences.get(heading.lower(), [])) == 1
        and bool(section_occurrences[0])
        and not _is_placeholder_section(section_occurrences[0])
        for heading in _BODY_SECTIONS_CANONICAL_KEYS
    )
    return FileBackedSourceIntake(
        references_ready=True,
        direct_ready=direct_ready,
        strict_steps=extract_steps_from_canonical(source_text) if direct_ready else None,
    )


def reject_unmatched_create_fence(
    source_text: str,
    source: Path | str,
    *,
    fence_scan: Optional[FencedCodeScan] = None,
) -> None:
    """Reject source prose whose unclosed fence would hide later H2 sections."""
    scan = fence_scan or _fenced_code_spans(_strip_frontmatter(source_text))
    if scan.unmatched_opening is not None:
        raise CreateError(
            f"{source}: unmatched opening code fence; add a matching closing fence "
            "before authoring."
        )


def reject_unmatched_create_sources(
    *,
    seed_body: Optional[str],
    from_description: Optional[str],
    source: Path | str,
) -> None:
    """Reject each independently supplied create source before it is read."""
    for source_text in (seed_body, from_description):
        if source_text is not None:
            reject_unmatched_create_fence(source_text, source)


class _CreateInterrupted(KeyboardInterrupt):
    """Interrupt carrying a target that must remain available for recovery."""

    def __init__(self, artifact: "_CreatedArtifact") -> None:
        super().__init__()
        self.artifact = artifact


@dataclass(frozen=True)
class RoadmapResearchTarget:
    """One recorded product row and its local research policy."""

    token: str
    product: str
    origin: str
    description: Optional[str]
    research_disclosure: Optional[ResearchDisclosure]


@dataclass(frozen=True)
class RoadmapResearchVerdict:
    """The source result retained for one roadmap product target."""

    target_token: str
    references: tuple["Reference", ...]
    source: str

    @property
    def is_local(self) -> bool:
        """Whether this deterministic no-source verdict stayed in-process."""
        return self.source == "local"


@dataclass
class CreateResult:
    # ``None`` on a file-backed split or refusal, where no plan is written.
    # A normal and every inline create sets it.
    plan_path: Optional[Path]
    manifest_path: Path
    manifest_updated: bool  # False when the path was already listed.
    # Provenance lifted from a canonical ``--from-existing`` source.
    # ``None`` for blank-skeleton creates and for non-canonical inputs.
    provenance: Optional[CanonicalProvenance] = None
    # New location of the seed's plan-details directory after rename,
    # or ``None`` when no rename occurred (no provenance, no existing
    # dir, slug unchanged, or rename skipped).
    plan_details_renamed_to: Optional[Path] = None
    # Human-readable reason a rename was skipped (collision, OSError).
    # ``None`` on success or when no rename was attempted.
    plan_details_skip_reason: Optional[str] = None
    # ``(original, archived)`` pairs from collision replacement — empty
    # when the create didn't replace anything.
    replaced_archives: list[tuple[Path, Path]] = field(default_factory=list)
    # Skip reasons from collision replacement (e.g. archive collision in
    # the archive dir itself). Empty on the happy path.
    replaced_skipped: list[str] = field(default_factory=list)
    # Manifest paths cleared when the existing plan(s) were replaced.
    replaced_manifest_entries: list[str] = field(default_factory=list)
    # Set when the distill first-pass determined the seed describes multiple
    # independent plans and create short-circuited with a split proposal
    # instead of writing a plan. ``None`` on the normal (single-plan) path.
    split_proposal: Optional["SplitProposal"] = None
    # The cleaned canonical-markdown text produced by the distill first-pass
    # on the single-plan path. ``None`` when distillation was skipped /
    # passthrough. The CLI archives it alongside the seed (superseded-by-new-
    # plan rule).
    distilled_seed: Optional[str] = None
    # Deliverable references in the distilled body that no acceptance
    # criterion pins down (see :func:`find_dropped_references`). Empty
    # unless the single-plan distill path ran and found dangling pointers.
    # Surfaced as a create-time warning; carried here so the CLI / callers
    # can re-report them in the final summary.
    dropped_references: list["DroppedReference"] = field(default_factory=list)
    # Likely misspellings in the plan slug / title (see
    # :func:`find_misspellings`). Empty when the optional spell-check
    # dependency isn't installed or nothing was flagged. Advisory only.
    misspellings: list["Misspelling"] = field(default_factory=list)
    # Set when post-publication reference research or step re-proposal fails.
    # The plan remains usable; the CLI exits 0 and the run log records it.
    iteration_stage_failure: Optional[str] = None
    # The selected terminal path for a ``--from-existing`` source. Inline
    # callers keep ``None`` so their legacy ``distill`` behavior stays local
    # to that input form.
    file_backed_route: Optional[FileBackedSourceRoute] = None
    # The route-owned result cache. Needed only to discard a refused result
    # without deleting an unrelated route's reusable response.
    route_checkpoint_name: Optional[str] = None
    # The preparation explanation for the ``refused`` route only.
    refusal_reason: Optional[str] = None


@dataclass
class _CreatePlanContinuation:
    """Prepared state used after publication, not by publication itself."""

    from_description: Optional[str]
    input_fn: InputFn
    distilled_seed: Optional[str]
    dropped_references: list[DroppedReference]
    misspellings: list[Misspelling]
    uncarried_distilled_guardrails: list[str] = field(default_factory=list)
    uncarried_synthesis_guardrails: list[str] = field(default_factory=list)


@dataclass
class PreparedCreatePlan:
    """Initial create state ready for publication."""

    plan: Plan
    output_dir: Path
    predicted_plan_path: Path
    manifest_path: Path
    collisions: list[Collision]
    should_replace: bool
    provenance: Optional[CanonicalProvenance]
    from_existing_path: Optional[Path]
    concept_tree: ConceptTree
    saved_concepts: Optional[ConceptTree]
    references: list[Reference]
    seed_sections: dict[str, str]
    synthesized_sections: Optional[dict[str, Optional[str]]]
    supplied_guardrails: dict[str, str]
    risk_profile_proposal: "_RiskProfileProposal"
    continuation: _CreatePlanContinuation
    file_backed_intake: Optional[FileBackedSourceIntake] = None
    file_backed_route: Optional[FileBackedSourceRoute] = None
    route_checkpoint_name: Optional[str] = None
    roadmap_research_targets: tuple[RoadmapResearchTarget, ...] = ()
    roadmap_research_verdicts: tuple[RoadmapResearchVerdict, ...] = ()
    references_body: Optional[str] = None
    direct_source_authority: Optional["_DirectSourceAuthority"] = None
    normalized_preparation_sections: Optional[dict[str, Optional[str]]] = None
    normalized_preparation_evidence_spans: Optional[
        dict[str, Optional[tuple[tuple[int, int], ...]]]
    ] = None


@dataclass
class _PublishedCreatePlan:
    """Durable create state used by convergence and finalization."""

    plan_path: Path
    concept_tree: ConceptTree
    plan_fingerprint: str
    signed_concept_scope: bool
    manifest_updated: bool
    plan_details_renamed_to: Optional[Path]
    plan_details_skip_reason: Optional[str]
    replaced_archives: list[tuple[Path, Path]]
    replaced_skipped: list[str]
    replaced_manifest_entries: list[str]


@dataclass(frozen=True)
class _CreatePlanConvergence:
    """Inputs owned by the post-publication convergence phase."""

    plan_path: Path
    repo_root: Path
    slug: str
    output_dir: Path
    from_description: Optional[str]
    input_fn: InputFn
    claude_invoker: ClaudeInvoker
    foundational_invoker: Optional[ClaudeInvoker]
    capture_scenarios: bool
    arm: Optional[str]
    budget: IterativeBudget
    allow_drift: bool
    auto_reconcile_on_drift: bool
    collision_sidecar: bool
    triage: bool
    include_info: bool
    skip_prose_reproposal: bool
    run_logger: Optional[RunLoggerLike]
    plan_fingerprint: str
    preserve_selected_roadmap_references: bool


@dataclass(frozen=True)
class SplitProposalEntry:
    """One proposed plan carved out of an oversize / multi-topic seed.

    ``start_line`` / ``end_line`` are 1-based inclusive line numbers into the
    seed handed to the distill pass; ``None`` when the model's range was
    unusable (out of range / inverted) and could not be clamped — the
    renderer then prints ``title`` + ``rationale`` without a carve command.
    """

    title: str
    suggested_slug: str
    rationale: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


@dataclass(frozen=True)
class SplitProposal:
    """A multi-plan split proposal returned by the distill first-pass.

    ``entries`` always has >= 2 items. ``saved_to`` is the path the proposal
    worksheet was written to (``None`` until the CLI saves it).
    """

    entries: list[SplitProposalEntry]
    saved_to: Optional[Path] = None


@dataclass(frozen=True)
class DirectSplitAssessment:
    """One raw-source decision for a direct file-backed create route."""

    split: Optional[list[SplitProposalEntry]] = None

    @property
    def is_single(self) -> bool:
        return self.split is None

    @property
    def is_split(self) -> bool:
        return self.split is not None


@dataclass(frozen=True)
class _DirectSourceAuthority:
    """Source ranges that direct publication must keep verbatim."""

    source_text: str
    seed_sections: dict[str, str]
    references_body: str


@dataclass(frozen=True)
class DistillOutcome:
    """One terminal result from file-backed source preparation.

    Model replies can produce only ``normalized`` or ``split``.  ``refused``
    is caller-owned after the bounded parser repair fails; it is never an
    empty payload that callers could accidentally treat as raw-source input.
    """

    outcome: Literal["normalized", "split", "refused"]
    sections: Optional[dict[str, Optional[str]]] = None
    evidence_spans: Optional[
        dict[str, Optional[tuple[tuple[int, int], ...]]]
    ] = None
    split: Optional[list[SplitProposalEntry]] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.outcome == "normalized":
            if (
                self.sections is None
                or self.evidence_spans is None
                or self.split is not None
                or self.reason is not None
            ):
                raise ValueError(
                    "normalized preparation requires sections and evidence spans only"
                )
        elif self.outcome == "split":
            if (
                self.split is None
                or self.sections is not None
                or self.evidence_spans is not None
                or self.reason is not None
            ):
                raise ValueError("split preparation requires split entries only")
        elif self.outcome == "refused":
            if (
                not self.reason
                or self.sections is not None
                or self.evidence_spans is not None
                or self.split is not None
            ):
                raise ValueError("refused preparation requires a reason only")
        else:
            raise ValueError(f"unknown preparation outcome {self.outcome!r}")

    @classmethod
    def normalized(
        cls,
        sections: dict[str, Optional[str]],
        evidence_spans: dict[str, Optional[tuple[tuple[int, int], ...]]],
    ) -> "DistillOutcome":
        """Build a validated normalized preparation result."""
        return cls(
            outcome="normalized",
            sections=sections,
            evidence_spans=evidence_spans,
        )

    @classmethod
    def split_proposal(cls, entries: list[SplitProposalEntry]) -> "DistillOutcome":
        """Build a validated multi-plan preparation result."""
        return cls(outcome="split", split=entries)

    @classmethod
    def refused(cls, reason: str) -> "DistillOutcome":
        """Build the explicit terminal result for failed preparation."""
        return cls(outcome="refused", reason=reason.strip() or "preparation failed")

    @property
    def is_normalized(self) -> bool:
        return self.outcome == "normalized"

    @property
    def is_split(self) -> bool:
        return self.outcome == "split"

    @property
    def is_refused(self) -> bool:
        return self.outcome == "refused"

    @property
    def distilled(self) -> Optional[str]:
        """Render normalized sections for legacy downstream consumers."""
        if self.sections is None:
            return None
        return _render_distilled_markdown(self.sections)


@dataclass(frozen=True)
class _RiskProfileProposal:
    """A pre-publication risk proposal for step 3 to review and persist."""

    profile: RiskProfile
    rationale: str
    minimum_profile: RiskProfile
    # ``low`` is only reviewable when the classifier admitted every positive
    # condition and found no source counter-signal. Keep those facts beside the
    # proposal so an incomplete model payload cannot become a lower declaration.
    low_admitted: bool = False
    source_counter_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RiskDeclaration:
    """One final pre-write risk declaration and how the operator chose it."""

    profile: RiskProfile
    rationale: str
    mode: str


@dataclass(frozen=True)
class _CreatedArtifact:
    """Recovery state for a target write that crossed create's safe boundary."""

    path: Path
    registered: bool
    parse_valid: bool


def shell_claude_invoker(prompt: str) -> str:
    """Production invoker for --from: captures stdout (not returncode).

    Delegates to :func:`plan_tool.shell.claude_invoke`, which logs claude's
    stderr on non-zero exit and returns ``""`` when the executable isn't
    on PATH (so this caller's downstream parsing falls back to interactive
    instead of raising).
    """
    _, stdout = claude_invoke(prompt)
    return stdout


_FILE_PATH_PATTERN = re.compile(
    r"`([^`\s]+/[^`\s]+\.[A-Za-z0-9]{1,8})`|"
    r"(?<![\w/])([A-Za-z0-9_.][A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})(?![\w/])"
)


def extract_file_path_candidates(text: str) -> list[Path]:
    r"""Find plausible repo-relative file paths in ``text``.

    Returns ``Path`` objects for each unique token that looks like a
    file path with a directory component and a file extension. Both
    backtick-fenced (e.g. \`amplify/data/resource.ts\`) and inline
    (``amplify/data/resource.ts``) forms are matched. Used by
    :func:`cmd_create` to decide whether a seed touches multiple repos
    and the plan needs a higher umbrella root than the cwd's ``.git``.

    The matching is deliberately permissive — false positives are
    cheap (they fail the "does this resolve under any candidate root?"
    check downstream), false negatives leave the umbrella under-
    detected and the plan registered under the wrong root.
    """
    seen: set[str] = set()
    out: list[Path] = []
    for match in _FILE_PATH_PATTERN.finditer(text):
        token = match.group(1) or match.group(2)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(Path(token))
    return out


def read_existing_description(path: Path) -> str:
    """Read the seed file in full and return its body.

    There is no size limit: the distill first-pass
    (``propose_distilled_seed_from_claude``) is the gate. An oversize seed is
    reorganized into a compact canonical body, or — when it spans multiple
    independent efforts — returned as a multi-plan split proposal.

    Resolves relative paths against the cwd (the CLI's responsibility —
    ``create_plan`` stays filesystem-agnostic for this argument).
    """
    if not path.is_file():
        raise CreateError(f"existing plan path is not a file: {path}")
    return path.read_text(encoding="utf-8")


@dataclass
class ArchiveResult:
    """Outcome of archiving an existing source file (and optional details).

    `archived` lists `(original, archived)` pairs that were successfully moved.
    `skipped` lists human-readable reasons for files that could not be moved
    (e.g. a filesystem error while writing the archive). Skips are
    surfaced as warnings rather than errors because the new plan is already on
    disk by the time archival runs — failing the whole command would leave the
    user worse off than letting them clean up manually.
    """

    archived: list[tuple[Path, Path]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def archive_existing_source(
    source: Path,
    new_plan_path: Path,
    *,
    repo_root: Optional[Path] = None,
    archive_dirname: str = ARCHIVE_DIRNAME,
) -> ArchiveResult:
    """Move `source` (and any matching plan-details/<slug>/ directory) to <source.parent>/archive/.

    Each archived markdown file gets a one-line notice prepended pointing at
    `new_plan_path`. The plan-details lookup uses the priority-prefix slug from
    the source filename (e.g. `1-foo.md` → slug `foo`); files outside that
    convention only get the source itself archived.
    """
    result = ArchiveResult()
    new_plan_display = display_path(new_plan_path, repo_root)
    archive_dir = source.parent / archive_dirname

    if not source.is_file():
        result.skipped.append(f"source no longer exists: {source}")
        return result

    slug = _slug_from_filename(source.name)
    details_src = (
        source.parent / "plan-details" / slug if slug is not None else None
    )
    has_details_bundle = details_src is not None and details_src.is_dir()

    try:
        archive_dir.mkdir(exist_ok=True)
    except OSError as exc:
        result.skipped.append(
            f"could not create archive directory {archive_dir}: {exc}"
        )
        return result
    archived_source, details_dst = _archive_targets(
        source, archive_dir, slug if has_details_bundle else None
    )

    content: str
    try:
        content = source.read_text(encoding="utf-8")
    except OSError as exc:
        result.skipped.append(f"could not archive {source}: {exc}")
        return result

    details_tmp: Optional[Path] = None
    detail_archived_pairs: list[tuple[Path, Path]] = []
    if has_details_bundle and details_src is not None and details_dst is not None:
        details_tmp = (
            details_dst.parent
            / f".{details_dst.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            details_tmp.parent.mkdir(parents=True, exist_ok=True)
            if details_tmp.exists():
                shutil.rmtree(details_tmp)
            details_tmp.mkdir()
            replacement = _replacement_notice(new_plan_display)
            detail_archived_pairs = _copy_details_bundle_for_archive(
                details_src,
                details_tmp,
                final_root=details_dst,
                replacement_notice=replacement,
            )
        except OSError as exc:
            if details_tmp is not None and details_tmp.exists():
                shutil.rmtree(details_tmp, ignore_errors=True)
            result.skipped.append(
                f"could not archive plan-details for slug {slug!r}: {exc}"
            )
            return result

    try:
        durable_write_text(
            archived_source,
            _replacement_notice(new_plan_display) + content,
        )
        source.unlink()
        if (
            details_tmp is not None
            and details_src is not None
            and details_dst is not None
        ):
            _publish_archive_dir(details_tmp, details_dst)
            shutil.rmtree(details_src)
        result.archived.append((source, archived_source))
        result.archived.extend(detail_archived_pairs)
    except OSError as exc:
        if details_tmp is not None and details_tmp.exists():
            shutil.rmtree(details_tmp, ignore_errors=True)
        if details_dst is not None and details_dst.exists():
            try:
                shutil.rmtree(details_dst)
            except OSError:
                pass
        if archived_source.exists() and source.exists():
            try:
                archived_source.unlink()
            except OSError:
                pass
        elif archived_source.exists() and not source.exists():
            try:
                durable_write_text(source, content)
                archived_source.unlink()
            except OSError:
                result.skipped.append(
                    f"manual recovery required after partial archive of {source}: {exc}"
                )
                return result
        result.skipped.append(f"could not archive {source}: {exc}")
        return result

    return result


def _copy_details_bundle_for_archive(
    details_src: Path,
    details_tmp: Path,
    *,
    final_root: Path,
    replacement_notice: str,
) -> list[tuple[Path, Path]]:
    """Copy a detail bundle into a private staging dir before publishing it."""
    archived: list[tuple[Path, Path]] = []
    for child in sorted(details_src.rglob("*")):
        rel = child.relative_to(details_src)
        target = details_tmp / rel
        final_target = final_root / rel
        if child.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if child.suffix.lower() == ".md":
            body = child.read_text(encoding="utf-8")
            target.write_text(replacement_notice + body, encoding="utf-8")
        else:
            target.write_bytes(child.read_bytes())
        archived.append((child, final_target))
    return archived


def _publish_archive_dir(source: Path, target: Path) -> None:
    """Publish a staged directory, preserving the no-overwrite target contract."""
    if target.exists():
        raise FileExistsError(f"archive target already exists: {target}")
    source.replace(target)


def _archive_targets(
    source: Path, archive_dir: Path, bundle_slug: Optional[str]
) -> tuple[Path, Optional[Path]]:
    """Return non-existing archive targets for a source and optional bundle.

    The first archive keeps the historical names:
    ``archive/<stem>.replaced.md`` and ``archive/plan-details/<slug>/``.
    When either side already exists, both sides move to the same numbered
    generation, e.g. ``<stem>.replaced.1.md`` and
    ``plan-details/<slug>.replaced.1/``. Choosing the pair before writing keeps
    the source file and its detail bundle together across repeated archives.
    """
    base_source = archive_dir / f"{source.stem}{REPLACED_SUFFIX}{source.suffix}"
    base_details = (
        archive_dir / "plan-details" / bundle_slug
        if bundle_slug is not None
        else None
    )
    if not base_source.exists() and (
        base_details is None or not base_details.exists()
    ):
        return base_source, base_details

    index = 1
    while True:
        source_target = (
            archive_dir
            / f"{source.stem}{REPLACED_SUFFIX}.{index}{source.suffix}"
        )
        details_target = (
            archive_dir / "plan-details" / f"{bundle_slug}{REPLACED_SUFFIX}.{index}"
            if bundle_slug is not None
            else None
        )
        if not source_target.exists() and (
            details_target is None or not details_target.exists()
        ):
            return source_target, details_target
        index += 1


def _slug_from_filename(name: str) -> Optional[str]:
    """`1-foo-bar.md` -> `foo-bar`. None when there's no priority-prefix."""
    from plan_tool.locator import slug_from_filename

    return slug_from_filename(name, default_to_stem=False)


def resolve_existing_plan_details(
    from_existing_path: Path,
    provenance: CanonicalProvenance,
) -> Optional[Path]:
    """Return the on-disk plan-details directory pointed to by ``provenance``.

    The path stored in provenance is relative to the canonical's parent
    (which is also ``from_existing_path.parent``, by the legacy
    convention that produced these provenance frontmatters).
    Returns ``None`` when provenance has no plan-details pointer or the
    directory is gone.
    """
    if provenance.plan_details is None:
        return None
    candidate = (from_existing_path.parent / provenance.plan_details).resolve()
    if not candidate.is_dir():
        return None
    return candidate


def rename_plan_details_to_slug(
    existing_details: Path,
    output_dir: Path,
    new_slug: str,
) -> tuple[Optional[Path], Optional[str]]:
    """Move ``existing_details`` to ``output_dir/plan-details/<new_slug>``.

    Returns ``(target, None)`` on success; ``(None, reason)`` when the
    rename is a no-op (target equals source — slug unchanged) or skipped
    (target exists or filesystem error). Skips are returned as
    human-readable reasons rather than raised exceptions because the
    caller has already written the new plan to disk — failing now would
    leave the user with a written plan and no way to retry the move.
    """
    target = (output_dir / "plan-details" / new_slug).resolve()
    if target == existing_details:
        return None, None
    if target.exists():
        return None, (
            f"plan-details rename target already exists: {target} "
            "(resolve manually and move existing details into place)"
        )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing_details.rename(target)
    except OSError as exc:
        return None, f"could not rename plan-details to {target}: {exc}"
    return target, None


def _replacement_notice(new_plan_display: str) -> str:
    return (
        f"> **Replaced**: this file has been superseded by "
        f"`{new_plan_display}`.\n"
        "> Preserved here for history; do not edit.\n\n"
    )


def validate_slug(slug: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise CreateError(
            f"invalid slug {slug!r}: must match {SLUG_RE.pattern} "
            "(lowercase letters/digits/dashes; ≥2 chars, starts and ends alphanumeric)"
        )


def unslugify(slug: str) -> str:
    """Derive a human-readable title from a slug.

    ``ai-coach-deep-linking`` → ``Ai Coach Deep Linking``. Used as the
    default for the title prompt so callers can press Enter to accept
    rather than retyping the slug words. Acronyms come out wrong
    (``AI`` → ``Ai``) — authors edit at the prompt when that matters.
    """
    return slug.replace("-", " ").title()


def slugify(text: str, *, max_words: int = 6) -> str:
    """Best-effort deterministic slug from arbitrary text.

    Lowercases, collapses every run of non-alphanumerics into a single
    dash, trims dashes off the ends, and keeps at most ``max_words``
    words so a whole paragraph doesn't become a 200-char slug. Returns
    ``""`` when nothing slug-worthy survives or the result is too short
    to satisfy :data:`SLUG_RE` (which requires ≥2 chars and alphanumeric
    ends) — the caller then has no deterministic suggestion to offer.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    if not slug:
        return ""
    slug = "-".join(slug.split("-")[:max_words])
    return slug if SLUG_RE.fullmatch(slug) else ""


def _first_meaningful_line(text: str) -> str:
    """First non-blank line of ``text`` with markdown heading/bullet markers stripped.

    Feeds the deterministic ``slugify`` fallback when claude can't be
    reached. ``# My Plan`` / ``- do the thing`` collapse to their prose.
    """
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").lstrip("-*").strip()
        if stripped:
            return stripped
    return ""


# Cap on the seed text fed to the slug-suggestion prompt. A slug only
# needs the gist; sending a whole multi-KB seed (the --from-existing
# case) wastes tokens and the model keys on the opening anyway.
_SLUG_PROMPT_CHARS = 4000


def _render_slug_prompt(description: str) -> str:
    return (
        "Suggest a short, descriptive slug for an implementation plan "
        "based on the description below.\n\n"
        "Rules for the slug:\n"
        "- lowercase letters, digits, and single dashes only\n"
        "- 2-5 words in kebab-case (e.g. `add-user-auth`, "
        "`refactor-cli-parser`)\n"
        "- no priority prefix, no `.md` suffix, no leading/trailing dash\n"
        "- name the outcome of the work, not the seed's format\n\n"
        "Respond with ONLY the slug on a single line — no backticks, no "
        "prose, no explanation.\n\n"
        f"Plan description:\n{description[:_SLUG_PROMPT_CHARS]}\n"
    )


def _parse_slug_response(raw: str) -> Optional[str]:
    """Pull a valid slug out of claude's single-line slug response.

    Takes the first non-blank line, strips surrounding backticks /
    whitespace, and normalizes through :func:`slugify` so a slightly
    off-spec answer (stray spaces, ``Add Foo``) still yields a usable
    slug. Returns ``None`` when nothing valid survives.
    """
    for line in raw.splitlines():
        candidate = line.strip().strip("`").strip()
        if not candidate:
            continue
        return slugify(candidate) or None
    return None


def suggest_slug(
    description: str,
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
) -> Optional[str]:
    """Suggest a slug for a plan from its description.

    Asks claude for a kebab-case slug; on an empty / unparseable response
    falls back to :func:`slugify` of the first meaningful line of the
    description. Returns ``None`` only when neither path yields a slug
    that satisfies :data:`SLUG_RE` (e.g. an empty description and a dead
    invoker) — the caller then asks the user to pass one explicitly.
    """
    if reporter is None:
        reporter = StderrReporter()
    handle = reporter.start_step(1, 1, "Suggesting a slug")
    start = time.monotonic()
    raw = invoker(_render_slug_prompt(description))
    elapsed = time.monotonic() - start
    slug = _parse_slug_response(raw) if raw else None
    if slug is None:
        slug = slugify(_first_meaningful_line(description)) or None
    if slug is None:
        handle.fail(elapsed, "no usable slug from claude or description")
        return None
    handle.complete(elapsed, len(slug.encode("utf-8")))
    return slug


def resolve_create_slug(
    provided: Optional[str],
    description: Optional[str],
    invoker: ClaudeInvoker,
    *,
    input_fn: InputFn = input,
    yes: bool = False,
    reporter: Optional[ProgressReporter] = None,
) -> str:
    """Return a validated slug, suggesting one when ``provided`` is None.

    When ``provided`` is given it is validated and returned unchanged, so
    the historical ``plan-tool create <slug>`` contract is untouched.
    When it is ``None`` a slug is suggested from ``description`` (see
    :func:`suggest_slug`) and offered to the user via ``input_fn``: press
    Enter to accept, or type a replacement (re-prompted until it
    validates). Under ``yes`` the suggestion is taken silently.

    Raises :class:`CreateError` when no slug was provided and none could
    be suggested — either because there is no ``--from`` /
    ``--from-existing`` description to derive one from, or because the
    suggestion machinery produced nothing usable. The message tells the
    user to pass a slug explicitly.
    """
    if provided is not None:
        validate_slug(provided)
        return provided
    if not (description and description.strip()):
        raise CreateError(
            "no slug given and no --from/--from-existing text to suggest "
            "one from; pass a slug explicitly (plan-tool create <slug> ...)"
        )
    suggestion = suggest_slug(description, invoker, reporter=reporter)
    if suggestion is None:
        raise CreateError(
            "no slug given and a slug could not be suggested from the "
            "description; pass a slug explicitly (plan-tool create <slug> ...)"
        )
    if yes:
        return suggestion
    while True:
        chosen = _ask(input_fn, f"Slug [{suggestion}]: ", default=suggestion)
        try:
            validate_slug(chosen)
        except CreateError as exc:
            print(exc)
            continue
        return chosen


def resolve_output_dir(
    repo_root: Path, override: Optional[Path] = None
) -> Path:
    if override is not None:
        p = override if override.is_absolute() else (repo_root / override)
        return p.resolve()
    return (repo_root / DEFAULT_OUTPUT_DIR).resolve()


@dataclass(frozen=True)
class Collision:
    """A file on disk that occupies a plan slug.

    ``registered`` reflects whether ``path`` (resolved) appears in the
    manifest the caller passed to :func:`find_collisions`. Callers that
    don't supply manifest context get ``registered=True`` so the
    pre-existing fail-fast behavior is preserved — see the docstring on
    :func:`find_collisions` for the rationale.
    """

    path: Path
    registered: bool


def find_collisions(
    output_dir: Path,
    slug: str,
    *,
    manifest_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> list[Collision]:
    """Return every existing file in ``output_dir`` that occupies ``slug``.

    Matches the unprefixed form (``<slug>.md``) plus any ``<digits>-<slug>.md``.
    The digit-prefix regex matches the priority-bucket prefixes (1=high,
    2=medium, 3=low) and also any legacy multi-digit prefixes that may
    still live on disk from earlier numbering schemes. Using a plain
    ``*-{slug}.md`` glob would false-positive on ``1-foo-bar.md`` when
    creating slug ``bar``, so we anchor the prefix to digits only.

    When ``manifest_path`` and ``repo_root`` are both supplied, each
    :class:`Collision`'s ``registered`` flag reflects whether the file is
    listed in the manifest. Without that context every hit is reported as
    ``registered=True`` so legacy callers keep the historical
    "any-collision-is-fatal" semantics.

    Returns an empty list when the directory doesn't exist or when no
    file occupies the slug — callers can branch on truthiness.
    """
    if not output_dir.is_dir():
        return []
    pattern = re.compile(rf"^\d+-{re.escape(slug)}\.md$")
    paths = [
        p for p in sorted(output_dir.iterdir())
        if p.is_file() and (p.name == f"{slug}.md" or pattern.match(p.name))
    ]
    if not paths:
        return []
    registered_set: set[Path] = set()
    have_manifest_ctx = manifest_path is not None and repo_root is not None
    if have_manifest_ctx:
        from plan_tool.locator import load_manifest_plan_paths

        registered_set = set(
            load_manifest_plan_paths(repo_root, manifest_path=manifest_path)
        )
    return [
        Collision(
            path=p,
            registered=(p.resolve() in registered_set) if have_manifest_ctx else True,
        )
        for p in paths
    ]


def check_collision(
    output_dir: Path,
    slug: str,
    *,
    manifest_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> None:
    """Raise :class:`FileExistsError` when ``slug`` is already in use.

    Convenience wrapper around :func:`find_collisions` that preserves the
    historical raise-on-first-hit contract callers still rely on (legacy
    test suites, scripted callers that want the hard stop). When the
    first collision is an orphan (file on disk but not registered in the
    manifest), the error message points at :func:`register_plan` so users
    have a clear recovery path.
    """
    hits = find_collisions(
        output_dir, slug, manifest_path=manifest_path, repo_root=repo_root
    )
    if not hits:
        return
    first = hits[0]
    if not first.registered:
        raise FileExistsError(
            f"a plan for slug {slug!r} already exists at {first.path} "
            f"but is not registered in the manifest. "
            f"Run `plan-tool register {first.path}` to adopt it, "
            f"or delete the file before re-running create."
        )
    raise FileExistsError(
        f"a plan for slug {slug!r} already exists: {first.path}"
    )


def validate_output_dir_in_repo(output_dir: Path, repo_root: Path) -> None:
    """Ensure the resolved output dir lives inside ``repo_root``.

    Called before any file is written so a misconfigured `--output-dir` doesn't
    leave an orphan plan on disk while `append_to_manifest` rejects the
    relative-path conversion.
    """
    try:
        output_dir.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise CreateError(
            f"output dir {output_dir} is not inside repo root {repo_root}"
        ) from exc


def validate_lessons_in_repo(lessons: str, repo_root: Path) -> None:
    """Refuse a ``lessons:`` path that resolves outside ``repo_root``.

    Mirrors :func:`validate_output_dir_in_repo`. Lessons are written to
    by ``run`` after each step, and the path is interpreted as
    repo-relative (or absolute). Letting an absolute path point outside
    the repo would leak per-step takeaways into a directory the user may
    not expect.
    """
    candidate = Path(lessons)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (repo_root / candidate).resolve()
    )
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise CreateError(
            f"lessons path {lessons!r} resolves to {resolved}, which is "
            f"not inside repo root {repo_root}"
        ) from exc


def _default_lessons_path(
    repo_root: Path, output_dir: Path, slug: str
) -> str:
    try:
        dir_rel = output_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        dir_rel = DEFAULT_OUTPUT_DIR
    return str(dir_rel / "plan-details" / slug / "lessons.md")


def _resolve_source_seed(
    from_existing_path: Optional[Path], repo_root: Path
) -> Optional[str]:
    """Repo-relative, verified-readable seed path for ``Plan.source_seed``.

    ``None`` for a blank-skeleton create, an inline ``--from`` string (no
    path), a seed outside the repo, or one that no longer exists — recording
    a guess is worse than recording nothing (BACKLOG #162).
    """
    if from_existing_path is None:
        return None
    if not is_within(from_existing_path, repo_root):
        return None
    resolved = from_existing_path.resolve()
    if not resolved.is_file():
        return None
    return resolved.relative_to(repo_root.resolve()).as_posix()


def prompt_metadata(
    input_fn: InputFn,
    *,
    default_lessons: str,
    default_title: str,
) -> tuple[str, Priority, Optional[str]]:
    title = _ask(
        input_fn,
        f"Title [{default_title}]: ",
        default=default_title,
    )
    priority_raw = _ask_choice(
        input_fn,
        "Priority (high/medium/low)",
        choices=("high", "medium", "low"),
        default="medium",
    )
    priority = Priority(priority_raw)
    wants_lessons = _ask_yn(input_fn, "Enable lessons log?", default=False)
    lessons: Optional[str] = None
    if wants_lessons:
        lessons = _ask(
            input_fn,
            f"Lessons path (repo-relative) [{default_lessons}]: ",
            default=default_lessons,
        )
    return title, priority, lessons


def prompt_steps(input_fn: InputFn) -> list[Step]:
    """Collect ≥1 step, then prompt for more until the user declines."""
    steps: list[Step] = []
    next_id = 1
    print("Add at least one step.")
    while True:
        existing_ids = {s.id for s in steps}
        steps.append(_prompt_one_step(input_fn, next_id, existing_ids, steps))
        next_id += 1
        if not _ask_yn(input_fn, "Add another step?", default=False):
            break
    return steps


def _ask_depends_on_notes(
    input_fn: InputFn,
    step_id: int,
    depends_on: list[int],
    prior_steps: list[Step],
) -> dict[int, str]:
    """Collect optional per-edge notes after ``depends_on`` is known."""
    if not depends_on:
        return {}
    by_id = {s.id: s for s in prior_steps}
    notes: dict[int, str] = {}
    for dep_id in depends_on:
        antecedent = by_id.get(dep_id)
        title_hint = f' ("{antecedent.title}")' if antecedent else ""
        answer = _ask(
            input_fn,
            f"Step {step_id} depends on step {dep_id}{title_hint}. "
            f"What does step {dep_id} deliver to this step? "
            f"(optional, blank to skip): ",
            default="",
        )
        if answer.strip():
            notes[dep_id] = answer.strip()
    return notes


def _prompt_one_step(
    input_fn: InputFn,
    step_id: int,
    existing_ids: set[int],
    prior_steps: Optional[list[Step]] = None,
) -> Step:
    title = _ask(input_fn, f"Step {step_id} title: ", required=True)
    complexity_raw = _ask_choice(
        input_fn,
        f"Step {step_id} complexity (low/medium/high, blank to skip)",
        choices=("low", "medium", "high", ""),
        default="",
    )
    complexity = Complexity(complexity_raw) if complexity_raw else None
    files_raw = _ask(
        input_fn,
        f"Step {step_id} files (comma-separated, blank for none): ",
        default="",
    )
    files = [f.strip() for f in files_raw.split(",") if f.strip()]
    depends_on = _ask_int_list(
        input_fn,
        f"Step {step_id} depends on (comma-separated ids, blank for none): ",
        valid_ids=existing_ids,
        self_id=step_id,
    )
    depends_on_notes = _ask_depends_on_notes(
        input_fn, step_id, depends_on, prior_steps or []
    )
    return Step(
        id=step_id,
        title=title,
        complexity=complexity,
        files=files,
        depends_on=depends_on,
        depends_on_notes=depends_on_notes,
    )


def extract_steps_from_canonical(text: str) -> Optional[list[Step]]:
    """Lift a ``Plan.steps`` list out of a canonical-layout source.

    Thin shim over :func:`plan_tool.canonical.extract_canonical_steps`:
    ids are assigned sequentially starting at 1, and the
    :class:`~plan_tool.canonical.CanonicalStep` ``title`` / ``files`` /
    ``creates`` / ``change_type`` / ``depends_on`` are copied verbatim.
    ``change_type`` is the plain ``Optional[str]`` from the canonical
    ``Type:`` line (``None`` when absent); pydantic coerces it to the
    ``ChangeType`` enum at the ``Step`` boundary. Returns ``None`` when
    the source doesn't match the strict canonical shape — caller falls
    back to the Claude path so non-canonical inputs continue to work
    unchanged.
    """
    canonical = extract_canonical_steps(text)
    if canonical is None:
        return None
    return [
        Step(
            id=i,
            title=cs.title,
            files=cs.files,
            creates=cs.creates,
            change_type=cs.change_type,
            depends_on=cs.depends_on,
        )
        for i, cs in enumerate(canonical, start=1)
    ]


def _summarize_step_graph_error(exc: PydanticValidationError) -> str:
    """One-line summary of why a proposed step list failed schema validation.

    The :class:`~plan_tool.schema.Plan` ``model_validator`` raises
    ``ValueError`` with specifics — ``step 4 depends_on references unknown
    id(s): [7]``, ``duplicate step ids: [2]``, ``step 3 cannot depend on
    itself``, cyclic-dependency messages. Pydantic wraps each as a
    ``"Value error, <msg>"`` entry in :meth:`~pydantic.ValidationError.errors`;
    this strips that prefix and joins the distinct messages so the actual
    cause lands in the ``handle.fail`` line and the run log instead of the
    generic "invalid graph". Falls back to a generic string if Pydantic
    ever emits an error with no message.
    """
    msgs: list[str] = []
    for err in exc.errors():
        msg = str(err.get("msg", "")).strip()
        prefix = "Value error, "
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
        if msg:
            msgs.append(msg)
    # dict.fromkeys de-dupes while preserving order (pydantic can repeat a
    # message across error entries for the same root cause).
    return "; ".join(dict.fromkeys(msgs)) or "schema validation failed"


def _note_discarded_repair(
    *,
    repo_root: Optional[Path],
    slug: Optional[str],
    phase: Optional[str],
    iteration: int,
    raw: str,
    reason: Optional[str],
    detail: Optional[str],
    run_logger: Optional[RunLoggerLike],
) -> None:
    """Record a repair response that failed and was discarded, without failing.

    The soft-rejection path restores the first proposal and carries on, so the
    ordinary ``steps is None`` diagnostics never run. A backend that reliably
    breaks on repair would otherwise be invisible: no dumped response, no
    ``parse_failure`` run-log row, and a run that reports success.
    """
    dump = _dump_failed_response(
        repo_root=repo_root,
        slug=slug,
        phase=phase or "propose_steps",
        iteration=iteration,
        raw=raw,
    )
    if run_logger is None or dump is None or repo_root is None:
        return
    extra: dict[str, object] = {"reason": reason, "iteration": iteration}
    if detail is not None:
        extra["detail"] = detail
    extra["discarded"] = True
    run_logger.parse_failure(
        phase="propose_steps",
        attempt=2,
        failure_path=str(dump.relative_to(repo_root)),
        **extra,
    )


def _dump_failed_response(
    *,
    repo_root: Optional[Path],
    slug: Optional[str],
    phase: str,
    iteration: int,
    raw: str,
) -> Optional[Path]:
    """Persist a rejected claude response under ``.plan-tool/parse-failures/``.

    Mirrors :func:`plan_tool.detail._log_parse_failure`'s convention so a
    failed create-phase response (unparseable step JSON, invalid step
    graph) lands in the same directory a debugging pass already checks.
    Without this, the only trace of the failure is the one-line ``FAILED``
    on stderr and the raw text — including whatever claude actually
    returned — is lost the moment the function returns ``None``.

    Best-effort: returns ``None`` and writes nothing when ``repo_root`` /
    ``slug`` are absent (the test-only callers that omit checkpoint
    context) or on any I/O error — a logging failure must never derail
    the create flow it exists to debug.
    """
    if repo_root is None or slug is None:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = repo_root / ".plan-tool" / "parse-failures" / slug
    dest_path = dest_dir / f"{phase}-iter{iteration}-{ts}.txt"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(raw, encoding="utf-8")
    except OSError:
        return None
    return dest_path


# Prompt-budget advisory for the create wizard's prose-heavy Claude phases.
# The create path sends from several sibling functions (distill / steps /
# synthesis / references) rather than one funnel like
# ``detail._author_step_detail``, so the warn-and-record is single-sourced
# here and called at each send site directly. Distill/steps/synthesis wire
# both their primary send and repair retry; references wires only its
# repair retry today — its primary send has no budget coverage. A repair
# that embeds its rejected response measures its larger prompt separately.
# ``active_context_window()`` is the selected model's window, else the leaf's default.
def _maybe_warn_create_budget(
    *,
    total_bytes: int,
    blocks: list[tuple[str, int]],
    phase: str,
    surface: str,
    repo_root: Optional[Path],
    plan_slug: str,
) -> bool:
    """Warn (stderr, warn/high only) + record the budget for one create phase.

    Best-effort: swallows its own errors so a formatter slip or an unwritable
    telemetry path never sinks a create run. Records only when ``repo_root`` is
    set (the recorder needs a root to write; tests often omit it).

    Returns whether the advisory completed. The caller gates the shell backstop
    on it (``suppress_prompt_budget_backstop(active=covered)``): a swallowed
    failure returns ``False`` so the generic backstop stays a fallback net
    rather than leaving the send with zero budget coverage.
    """
    try:
        budget = maybe_warn_prompt_budget(
            total_bytes,
            context_window=active_context_window(),
            blocks=blocks,
            surface=surface,
        )
        if repo_root is not None:
            record_prompt_budget(
                repo_root,
                plan_slug=plan_slug,
                phase=phase,
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


def _steps_missing_intent(steps: list[Step]) -> list[int]:
    """1-based array positions of proposed steps carrying no usable ``intent``.

    Positions, not ids: the proposal prompt tells the model ids are assigned by
    the caller, so a correction naming an id would point at nothing the model
    emitted. ``review.is_usable_intent`` is the sole judge of what counts.
    """
    return [
        i
        for i, step in enumerate(steps, start=1)
        if not is_usable_intent(step.intent)
    ]


def _missing_intent_rejection(steps: list[Step], positions: list[int]) -> str:
    """One-line rejection reason naming each offending step by position+title."""
    named = "; ".join(f"#{p} ({steps[p - 1].title})" for p in positions)
    return f"these steps carry no `intent`: {named}"


# Per-kind correction tails for the single ``propose_steps_from_claude`` repair
# retry. The retry prompt is read without the surrounding report, so each tail
# restates the requirement rather than only naming the offenders. Corrections
# replace, never accumulate — one retry, one tail.
_REPAIR_CORRECTION_GRAPH = (
    "Return a corrected JSON array of steps. Every `depends_on` entry must "
    "reference an existing step `id`; no self-dependencies, no duplicate "
    "ids; the whole response must be valid JSON. Each `depends_on` entry "
    "should use a bare JSON integer (`1`); quoted numerals are tolerated, but "
    "non-numeric or malformed numeral strings are not."
)
_REPAIR_CORRECTION_INTENT = (
    "Return the corrected JSON array of steps. Keep the steps you proposed "
    "and add what is missing: **every object needs a non-empty `intent`** — "
    "one line, present tense, on why that step exists. `TODO`, `TBD`, and an "
    "empty string do not count. The whole response must be valid JSON."
)


def _project_context_block(repo_root: Optional[Path]) -> str:
    """Return confirmed project context when the caller has a repository."""
    return project_profile_context(repo_root) if repo_root is not None else ""


def propose_steps_from_claude(
    description: str,
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
    repo_root: Optional[Path] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
    iteration: int = 0,
    rationales_out: Optional[dict[int, str]] = None,
    depends_on_notes_key_present_out: Optional[dict[int, bool]] = None,
    foundational_invoker: Optional[ClaudeInvoker] = None,
    capture_scenarios: bool = False,
    arm: Optional[str] = None,
) -> Optional[list[Step]]:
    """Ask claude for initial steps.

    Returns None when the response won't parse OR when the proposed steps form
    an invalid graph (unknown `depends_on`, self-dep, duplicate ids). Either
    failure falls back to interactive authoring. Either failure also reports
    ``fail`` on the progress handle before returning, so the user sees a
    closing line on stderr (instead of the call appearing to hang silently
    until the wizard prints its fallback notice).

    A live proposal whose steps carry no usable ``intent`` is a third, **soft**
    rejection: it spends the same single repair attempt as the two above, and
    the valid steps are returned either way. At most two invoker calls total.

    When ``repo_root`` is provided, the accumulated lessons from
    ``.plan-tool/lessons/`` are loaded and injected into the prompt so
    claude can apply rules from prior runs. Tests typically omit
    ``repo_root`` to keep prompts deterministic.

    When ``slug``, ``output_dir``, and ``repo_root`` are all provided the
    response is memoized under
    ``.plan-tool/checkpoints/<slug>/create-initial-steps.json``. A hit on a
    checkpoint whose ``input_hash`` matches slug + description + output dir +
    confirmed project context returns the cached raw response without invoking
    claude. ``resume=False`` skips the load but still saves on success — so a
    ``--no-resume`` run primes the cache for the next run. Tests that omit
    ``slug`` / ``output_dir`` get the historical no-checkpoint behavior.
    """
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    lessons_block = (
        render_lessons_block(load_lessons(repo_root)) if repo_root is not None else ""
    )
    project_context = _project_context_block(repo_root)
    # Combined (legacy) by default; the inline foundational item is dropped
    # only for the split arm, signalled by a wired split invoker. This keeps
    # the proposal from both inlining the item AND issuing its separate call.
    prompt = _render_from_prompt(
        description,
        lessons_block=lessons_block,
        project_context=project_context,
        omit_foundational_item=foundational_invoker is not None,
    )

    # Checkpoint lookup. Three-way gate: requires slug + output_dir +
    # repo_root to know where to write/read; ``resume`` then gates the load.
    # Save side runs even when ``resume=False`` so a no-resume run primes
    # the cache for the next invocation (matches step 2's contract).
    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _initial_steps_input_hash(
            slug,
            description,
            output_dir,
            repo_root,
            project_context=project_context,
            iteration=iteration,
        )
        # Iteration > 0 shards under a per-round filename so a later
        # round's save doesn't clobber an earlier round's evidence on
        # disk. Round 0 keeps the historical filename so pre-iteration
        # checkpoints still resume cleanly.
        ckpt_name = (
            _INITIAL_STEPS_CHECKPOINT_NAME
            if iteration == 0
            else f"{_INITIAL_STEPS_CHECKPOINT_NAME}-iter{iteration}"
        )
        ckpt_path = checkpoint_path(repo_root, slug, ckpt_name)

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if (
        cached is not None
        and run_logger is not None
        and input_hash is not None
    ):
        run_logger.checkpoint_hit(
            _INITIAL_STEPS_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    # TTY-gated resume confirmation. Non-TTY callers (CI / piped / tests
    # whose stdin is not a tty) auto-accept the cached body — re-prompting
    # in non-interactive contexts would deadlock on ``input()``. Under
    # ``--yes`` the silent input_fn returns "" → default-yes, so the
    # behavior matches.
    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached initial-steps proposal (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _INITIAL_STEPS_CHECKPOINT_NAME, "force"
                )
            cached = None

    # False unless the else-branch advisory ran; gates the backstop on the
    # primary send only. The repair retry below measures its own (larger)
    # prompt and gates on that result, so even a cached-hit-then-repair send is
    # covered by the scoped advisory rather than the generic backstop.
    budget_covered = False
    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Proposing initial steps (resumed from checkpoint)"
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        prompt_bytes = len(prompt.encode("utf-8"))
        steps_blocks = [("description", len(description.encode("utf-8")))]
        if lessons_block:
            steps_blocks.append(("lessons", len(lessons_block.encode("utf-8"))))
        if project_context:
            steps_blocks.append(
                ("project-context", len(project_context.encode("utf-8")))
            )
        budget_covered = _maybe_warn_create_budget(
            total_bytes=prompt_bytes,
            blocks=steps_blocks,
            phase="create-steps",
            surface="create step proposal",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        if run_logger is not None:
            run_logger.install_call_end_sink(phase="propose_steps", attempt=1)
        try:
            handle = reporter.start_step(
                1, 1, "Proposing initial steps",
                phase="propose_steps",
                attempt=1,
                prompt_bytes=prompt_bytes,
                prompt_sha256=hash_prompt(prompt),
            )
            start = time.monotonic()
            with suppress_prompt_budget_backstop(active=budget_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_steps",
                    attempt=1,
                    start=start,
                )
            elapsed = time.monotonic() - start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()

    # Always track omit-vs-``{}`` for soft-repair note merge even when the
    # caller did not request the out-map (first-authoring path).
    notes_key_tracker: dict[int, bool] = (
        depends_on_notes_key_present_out
        if depends_on_notes_key_present_out is not None
        else {}
    )

    def _attempt_parse_validate(raw_text: str):
        """Parse + graph-validate one raw response.

        Returns ``(steps, err_msg, phase, reason, detail)``; ``steps`` is
        ``None`` on failure with the other fields describing it (``detail``
        is ``None`` for the unparseable case).
        """
        parsed = _parse_steps_json(
            raw_text,
            rationales_out=rationales_out,
            depends_on_notes_key_present_out=notes_key_tracker,
        )
        if parsed is None:
            return (
                None,
                "claude returned an unparseable response",
                "propose-steps-unparseable",
                "unparseable_steps_json",
                None,
            )
        try:
            Plan(
                title="dry-run",
                status=PlanStatus.PLANNING,
                priority=Priority.LOW,
                steps=parsed,
            )
        except PydanticValidationError as exc:
            detail = _summarize_step_graph_error(exc)
            return (
                None,
                f"proposed steps form an invalid graph: {detail}",
                "propose-steps-invalid-graph",
                "invalid_step_graph",
                detail,
            )
        return (parsed, None, None, None, None)

    steps, err_msg, fail_phase, fail_reason, fail_detail = (
        _attempt_parse_validate(raw)
    )
    attempt = 1
    # Soft rejection: a valid graph whose steps carry no usable ``intent``.
    # Scoped to a LIVE proposal — a cached body predates the prompt's ``intent``
    # key (``_initial_steps_input_hash`` deliberately doesn't key on the prompt
    # text) and the save block below is gated on ``cached is None``, so
    # retrying a resume would spend a call whose better body is never written
    # back, and every later resume of the slug would spend it again. A resumed
    # intent-less body is left to the ``intent-presence`` finding.
    missing_intent = (
        _steps_missing_intent(steps)
        if steps is not None and cached is None
        else []
    )
    # One repair retry (mirrors ``propose_body_sections``): feed the
    # rejected response + the specific error back and ask for a corrected
    # graph. An unparseable response or an invalid graph is often a
    # transient model slip a single repair pass fixes -- far cheaper than
    # aborting the whole iteration loop on it. A missing ``intent`` is a third
    # rejection kind sharing that ONE budget, so authoring an intent adds no
    # round-trip of its own.
    if steps is None or missing_intent:
        if steps is None:
            # Hard rejection — nothing valid to fall back to.
            rejection, correction, keep_on_failure = (
                err_msg,
                _REPAIR_CORRECTION_GRAPH,
                None,
            )
        else:
            # Soft rejection — the graph is good, so a worse retry must not
            # lose it. ``raw`` and the rationales ride along: the checkpoint
            # payload has to be the body whose steps are returned, or a
            # ``--resume`` replays a body the previous run never used.
            rejection = _missing_intent_rejection(steps, missing_intent)
            correction = _REPAIR_CORRECTION_INTENT
            # Snapshot note-key presence with the graph: attempt 2 clears
            # ``notes_key_tracker`` before re-parse, and a re-decompose
            # fallback must restore omit-vs-``{}`` flags that match the kept
            # steps (see ``_preserve_on_disk_step_fields``).
            keep_on_failure = (
                steps,
                raw,
                dict(rationales_out or {}),
                dict(notes_key_tracker),
            )
        handle.notice(
            f"initial-steps: first attempt rejected ({rejection}); "
            "retrying once",
            kind="retry",
        )
        repair_prompt = (
            prompt
            + "\n\n## Repair\n\nYour previous response was REJECTED: "
            + rejection
            + "\n\nPrevious response:\n\n"
            + raw
            + "\n\n"
            + correction
        )
        if run_logger is not None:
            run_logger.claude_call_start(
                phase="propose_steps", attempt=2,
                prompt_bytes=len(repair_prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(repair_prompt),
            )
            run_logger.install_call_end_sink(phase="propose_steps", attempt=2)
        # The repair prompt appends the full rejected response, so it can be
        # materially larger than the primary — measure IT (not the stale
        # primary ``budget_covered``) so an oversized repair still gets a
        # scoped advisory, then suppress the generic backstop on that result.
        repair_covered = _maybe_warn_create_budget(
            total_bytes=len(repair_prompt.encode("utf-8")),
            blocks=[("rejected-response", len(raw.encode("utf-8")))],
            phase="create-steps",
            surface="create step proposal",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        try:
            retry_start = time.monotonic()
            with suppress_prompt_budget_backstop(active=repair_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(repair_prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_steps",
                    attempt=2,
                    start=retry_start,
                    base_elapsed=elapsed,
                )
            elapsed += time.monotonic() - retry_start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()
        attempt = 2
        # ``_parse_steps_json`` only ever *adds* to ``rationales_out``, so
        # attempt 1's entries would otherwise survive under attempt 2's ids —
        # handing the change-type wizard a defense written about a superseded
        # step, and phantom ids for steps the repair dropped.
        if rationales_out is not None:
            rationales_out.clear()
        notes_key_tracker.clear()
        steps, err_msg, fail_phase, fail_reason, fail_detail = (
            _attempt_parse_validate(raw)
        )
        if keep_on_failure is not None:
            # Soft rejection: the first graph was already valid, so the repair
            # is only licensed to ADD intents to it. Take the repair when it
            # parses and leaves the decomposition alone; otherwise restore the
            # first proposal verbatim. Without the title check a repair that
            # re-decomposed — nine well-formed steps answered with three coarse
            # ones that happen to carry intents — silently replaces a graph the
            # operator is never shown.
            (
                prior_steps,
                prior_raw,
                prior_rationales,
                prior_notes_key_present,
            ) = keep_on_failure
            same_decomposition = steps is not None and [
                s.title for s in steps
            ] == [s.title for s in prior_steps]
            if not same_decomposition:
                if steps is None:
                    # The repair genuinely failed. Record it before restoring —
                    # the restore is why the ``if steps is None`` block below
                    # cannot, and a backend that always breaks on repair would
                    # otherwise leave no artifact and no run-log entry at all.
                    _note_discarded_repair(
                        repo_root=repo_root,
                        slug=slug,
                        phase=fail_phase,
                        iteration=iteration,
                        raw=raw,
                        reason=fail_reason,
                        detail=fail_detail,
                        run_logger=run_logger,
                    )
                else:
                    handle.notice(
                        "initial-steps: repair re-decomposed the plan "
                        f"({len(prior_steps)} steps -> {len(steps)}); keeping "
                        "the first proposal and leaving the intents to the "
                        "`intent-presence` finding",
                        kind="retry",
                    )
                steps, raw = prior_steps, prior_raw
                if rationales_out is not None:
                    rationales_out.clear()
                    rationales_out.update(prior_rationales)
                notes_key_tracker.clear()
                notes_key_tracker.update(prior_notes_key_present)
                err_msg = fail_phase = fail_reason = fail_detail = None
            else:
                # Same titles: repair may omit optional ``depends_on_notes``;
                # preserve attempt-1 notes when the key was omitted (explicit
                # ``{}`` still clears — same rule as iterate preserve).
                assert steps is not None
                merged: list[Step] = []
                for repair_step, prior_step in zip(steps, prior_steps):
                    if (
                        not notes_key_tracker.get(repair_step.id, False)
                        and prior_step.depends_on_notes
                    ):
                        allowed = set(repair_step.depends_on)
                        preserved = {
                            k: v
                            for k, v in prior_step.depends_on_notes.items()
                            if k in allowed
                        }
                        repair_step = repair_step.model_copy(
                            update={"depends_on_notes": preserved}
                        )
                    merged.append(repair_step)
                steps = merged

    if steps is None:
        dump = _dump_failed_response(
            repo_root=repo_root,
            slug=slug,
            phase=fail_phase,
            iteration=iteration,
            raw=raw,
        )
        hint = (
            f" (raw response saved to {dump.relative_to(repo_root)})"
            if dump else ""
        )
        handle.fail(elapsed, f"{err_msg}{hint}")
        if run_logger is not None and dump is not None:
            extra = {"reason": fail_reason, "iteration": iteration}
            if fail_detail is not None:
                extra["detail"] = fail_detail
            run_logger.parse_failure(
                phase="propose_steps",
                attempt=attempt,
                failure_path=str(dump.relative_to(repo_root)),
                **extra,
            )
        # Capture the FAILURE as a scenario — the inputs that broke this arm are
        # re-runnable and the most discriminating A/B case. ``CATEGORY_FAILURE``
        # makes it pass the relevance gate (no steps to categorize structurally).
        if capture_scenarios and cached is None:
            capture_scenario(
                "propose_steps",
                experiment=PROMPT_MODE_EXPERIMENT.name,
                arm=arm_from_split(arm, split=foundational_invoker is not None),
                categories=[CATEGORY_FAILURE],
                inputs={"description": description},
                outcome={"status": "failed", "reason": fail_reason},
                repo_root=repo_root,
                run_id=getattr(run_logger, "run_id", None),
            )
        return None

    # Foundational-logic sweep (the divergent repo-wide duplication search,
    # lifted out of ``_render_from_prompt`` item 9). Opt-in via a dedicated
    # ``foundational_invoker`` (mirrors ``lessons_invoker`` on
    # ``generate_detail``). OFF by default (``combined`` arm); wired by the
    # real, shipped ``--prompt-mode split`` CLI surface (``cli/authoring.py``),
    # not merely an eval harness — pending objective A/B measurement of
    # whether split beats combined. Also gated on ``repo_root`` (the sweep
    # needs a tree to Grep) and on ``cached is None`` (a checkpoint resume must
    # not spawn a fresh call). A sweep that returns nothing — or whose merged
    # steps fail graph re-validation — leaves the proposal untouched: a
    # duplication suggestion must never sink an otherwise-valid step list.
    # Residual gap, reachable via ``--prompt-mode split`` today: the appended
    # consolidation step runs after ``_steps_missing_intent``'s forced
    # same-call repair (above), so if the model leaves both intent and
    # rationale unusable it ships with intent=None. Not a same-call repair
    # guarantee — only the TTY-gated ``_offer_missing_intents`` backstop
    # plus the ``tool()`` warning below, so a non-interactive/no-``--yes``
    # run at least surfaces it rather than shipping silently.
    if (
        foundational_invoker is not None
        and repo_root is not None
        and cached is None
    ):
        try:
            sweep = run_foundational_logic_sweep(
                _render_sweep_context(steps, description),
                foundational_invoker,
                run_logger=run_logger,
            )
            merged = merge_sweep_into_steps(steps, sweep, repo_root=repo_root)
            consolidation_was_merged = len(merged) > len(steps)
            if merged is not steps:
                Plan(
                    title="dry-run",
                    status=PlanStatus.PLANNING,
                    priority=Priority.LOW,
                    steps=merged,
                )
                if (
                    sweep is not None
                    and consolidation_was_merged
                    and merged[-1].intent is None
                ):
                    # The residual gap the comment above names, made
                    # visible instead of silent: neither field cleared
                    # is_usable_intent, so this step skipped the guarantee
                    # ordinary steps get.
                    tool(
                        f"foundational-logic sweep's consolidation step "
                        f"{merged[-1].id!r} has no usable intent (model "
                        f"supplied neither); review before running"
                    )
                steps = merged
        except PydanticValidationError:
            tool(
                "foundational-logic sweep produced an invalid step graph; "
                "keeping the un-merged proposal"
            )
        except Exception as exc:  # noqa: BLE001 — never sink create on a sweep slip
            tool(f"foundational-logic sweep failed ({exc}); skipping")

    # Save AFTER both parse and graph-validation pass. A cached unparseable
    # or graph-broken response would lock the user out of a real claude
    # retry — keep the cache only on full-success bodies. Best-effort:
    # a permissions / disk error here shouldn't abort an otherwise-
    # successful create that just won't be cheaply resumable next time.
    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save initial-steps checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _INITIAL_STEPS_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )

    handle.complete(elapsed, len(raw.encode("utf-8")))
    # Record the scenario (re-runnable: the description + which arm ran) for the
    # prompt-mode A/B corpus — but only for an operator-initiated run
    # (``capture_scenarios``, set by ``cmd_create``, NOT by bench / reconcile),
    # when it is RELEVANT (categorized), and not a checkpoint resume. No-op
    # unless PLAN_TOOL_CAPTURE_SCENARIOS is also set.
    if capture_scenarios and cached is None:
        categories = categorize_scenario(_proposal_scenario_signals(steps))
        capture_scenario(
            "propose_steps",
            experiment=PROMPT_MODE_EXPERIMENT.name,
            arm=arm_from_split(arm, split=foundational_invoker is not None),
            categories=categories,
            inputs={"description": description},
            outcome={"n_steps": len(steps), "titles": [s.title for s in steps]},
            repo_root=repo_root,
            run_id=getattr(run_logger, "run_id", None),
        )
    return steps


def _proposal_scenario_signals(steps: list[Step]) -> dict[str, bool]:
    """Detect which A/B behaviors a proposal exercised (for scenario capture).

    Signals are derived from the proposal STRUCTURE only — never from the
    split-only sweep output — so the categories are **arm-independent**: the
    same input tagged the same way regardless of which arm captured it (so the
    replay consumer can build balanced per-category cohorts). Signals:
    - ``mixed-step`` — a refactor→feature split (a FEATURE step that
      ``depends_on`` a REFACTOR step — the type-pure split signature, produced
      by the inline classification in both arms).
    - ``foundational-logic`` — any step has the shared-logic footprint (see
      :func:`step_has_foundational_footprint`).
    """
    by_id = {s.id: s for s in steps}
    has_mixed = any(
        s.change_type == ChangeType.FEATURE
        and any(
            by_id.get(d) is not None
            and by_id[d].change_type == ChangeType.REFACTOR
            for d in s.depends_on
        )
        for s in steps
    )
    return {
        CATEGORY_FOUNDATIONAL: any(
            step_has_foundational_footprint(s) for s in steps
        ),
        CATEGORY_MIXED_STEP: has_mixed,
    }


# Fixed item 7 (per-step intent). Always present in both arms — the intent
# rides the proposal call ``create`` already makes rather than costing a second
# round-trip, so it is numbered ahead of the dynamic tail below.
_PROPOSAL_INTENT_ITEM = (
    "Give every step a one-line `intent`: **why the step exists**, in the "
    "present tense, in plain words — the outcome it buys, stated so a "
    "reader who has not seen this description knows what the step is for. "
    "Do not confuse it with `rationale`: `rationale` defends the "
    "`change_type` classification (why the step's code is purely refactor "
    "or purely feature); `intent` says why the step is in the plan at all. "
    "Every step needs one — never `TODO`, `TBD`, or an empty string."
)

# Rides the JSON contract beside ``depends_on`` (not a numbered item).
_PROPOSAL_DEPENDS_ON_NOTES_EXPLAINER = (
    "When a step lists `depends_on`, it may include `depends_on_notes` "
    "mapping each antecedent id to one line naming what that antecedent "
    "delivers to this step; omit the key, or omit individual ids, when "
    "nothing needs saying — never require a note and do not invent notes "
    "for ordering-only edges."
)

# Fixed item 8 (destructive-operation disposition), riding both arms. Targets
# `description`/a dedicated step, never `intent` (reserved for the one-line
# why-this-step-exists statement) — avoid a hand-typed item-number
# cross-reference here; the last renumber already nearly missed one
# stale reference elsewhere (BACKLOG #268).
_PROPOSAL_DESTRUCTIVE_ITEM = (
    "**Enumerate destructive operations on every write path a step "
    "modifies or retires.** For each step whose `files:` touch code that "
    "deletes, overwrites, truncates, or wholesale-replaces artifacts "
    "(Grep those files for the delete/replace/cleanup calls), state what "
    "happens to each destructive operation under the new design — "
    "preserved, narrowed, or retired — by naming the disposition in the "
    "step's `description`, or by adding a dedicated step linked with "
    "`depends_on` when it needs more room than the description can hold. Do not "
    "fold it into `intent`, which is reserved for the one-line "
    "why-this-step-exists statement. Watch "
    "especially for a step that retires or bypasses a producer while an "
    "existing destructive consumer keeps running: state what that "
    "consumer now does on the new (possibly empty) input. A destructive "
    "operation left implicit is the defect class later audits return as "
    "CRITICAL. Fold the disposition into `description` or a dedicated step, "
    "never a new JSON key and never `intent`."
)

_REFACTOR_BOUNDARY_RULE = (
    "For behavior-preserving `refactor` work, select a distinct observable "
    "execution boundary before making it a step: a dispatch, lifecycle, "
    "ordered tail, terminal outcome, or another independently observable "
    "contract. Keep a repeated guard, accumulator, selector, rebuild, "
    "callback, or fixture in its observable owner's detail; promote it only "
    "when it independently owns an observable handoff, ordering, or bypass "
    "contract. When the available code does not ground a "
    "public-entry-to-terminal path, keep the one-concern guidance: do not "
    "invent an outer boundary or phase count, and do not promote an inner "
    "mechanism merely because it repeats."
)

_FOUNDATIONAL_REFACTOR_GUIDANCE = (
    "For a `refactor` suggestion, apply Stage 3's boundary rule here: "
    "shared logic becomes a separate step only when it names an observable "
    "execution boundary or independently owns an observable handoff, ordering, "
    "or bypass contract; otherwise leave it with its observable owner."
)

_MECHANISM_REACH_RULE = (
    "Classify mechanism reach from the focused property, not structural "
    "proxies: reuse a current common owner unchanged when its existing "
    "contract already makes the property true; otherwise allow the smallest "
    "local adapter or bounded additive extension that keeps existing consumer "
    "behavior and schema interpretation unchanged; otherwise leave a required "
    "shared semantic change out of the focused plan as separate work. An "
    "available local adapter does not rule out a compatible bounded additive "
    "extension, and common ownership does not require a local duplicate when "
    "unchanged reuse works. A shared path, duplicate, parallel caller, "
    "relation label, or number of consumers is inspection evidence only; none "
    "proves shared semantic reach."
)

# Inline item 9 (foundational-logic surfacing). Present in COMBINED mode; in
# SPLIT mode it is omitted and ``run_foundational_logic_sweep`` runs it as a
# separate call instead. It is the last item, so omitting it never leaves a
# numbering gap.
_PROPOSAL_FOUNDATIONAL_ITEM = (
    "**Identify the plan's foundational logic** — the core "
    "behavior or rule this plan adds or changes (a validation "
    "predicate, a parsing routine, a dispatch branch, a formatting "
    "rule), stated in one phrase — then use the same Glob/Grep audit "
    "from items 1-2 to grep the rest of the app for **other "
    "locations that share that logic**: duplicated blocks, parallel "
    "call sites, sibling modules implementing the same rule. Apply the "
    "mechanism-reach rule above before deciding whether a shared location "
    "belongs in this focused plan. Only fold compatible focused work into the "
    "relevant step's `files:` list (using the full path "
    "from the repo root, per item 1). "
    f"{_FOUNDATIONAL_REFACTOR_GUIDANCE} These are suggestions, not mandatory "
    "edits, and they ride inside the existing "
    "`files:`/`creates:`/new-step shapes — never add a new JSON "
    "key for them."
)


_STEP_PROPOSAL_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    example=[{
        "description": "plain-language step description",
        "complexity": "medium",
        "change_type": "feature",
        "rationale": "why this is feature work",
        "intent": "why this step exists",
        "files": ["existing/path.py"],
        "creates": ["new/path.py"],
        "depends_on": [],
        "depends_on_notes": {},
    }, {
        "description": "a later step depending on the one above",
        "complexity": "low",
        "change_type": "feature",
        "rationale": "why this is feature work",
        "intent": "why this step exists",
        "files": [],
        "creates": ["new/other_path.py"],
        # 1-based response positions; notes use the same ids as JSON-object keys.
        "depends_on": [1],
        "depends_on_notes": {"1": "what step 1 delivers to this step"},
    }],
)
_REFERENCE_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    example=[{
        "title": "official reference title",
        "url": "https://docs.example.com/reference",
        "description": "what the reference covers",
    }],
)
_ROADMAP_REFERENCE_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    example=[{
        "token": "target-token",
        "references": [{
            "title": "official reference title",
            "url": "https://docs.example.com/reference",
            "description": "what the reference covers",
        }],
    }, {
        "token": "another-target-token",
        "references": [],
    }],
)


def _render_from_prompt(
    description: str,
    *,
    lessons_block: str = "",
    project_context: str = "",
    omit_foundational_item: bool = False,
) -> str:
    """Render the step-proposal prompt.

    Defaults to the **combined** prompt: items 1-9, including the inline
    foundational-logic (item 9) instructions. ``omit_foundational_item``
    drops item 9 for the **split** A/B arm, where
    ``run_foundational_logic_sweep`` runs it as a separate call instead;
    items 1-8 are identical across the two arms. The flag is driven by
    whether the split invoker is wired (see
    :func:`propose_steps_from_claude`), so the proposal never both inlines
    the item AND issues its separate call.
    """
    lessons_section = (
        "\n\n## Accumulated lessons\n\n"
        f"{lessons_block.strip()}\n"
        if lessons_block.strip()
        else ""
    )
    project_context_section = (
        f"\n\n{project_context.strip()}" if project_context.strip() else ""
    )
    # Item 9 (foundational) is the last item, so omitting it in split mode
    # never leaves a numbering gap.
    tail_items = (
        f"9. {_PROPOSAL_FOUNDATIONAL_ITEM}\n\n" if not omit_foundational_item else ""
    )
    depends_on_notes_explainer = f"{_PROPOSAL_DEPENDS_ON_NOTES_EXPLAINER} "
    return (
        "Propose an initial plan step-list for this implementation plan.\n\n"
        "**Audit the codebase before answering.** This proposal is the "
        "foundation every later phase (detail drafts, jira stories, "
        "execution) builds on, so its file paths and complexity claims "
        "have to match what's actually on disk — not what the description "
        "prose implies. **Keep the proposal true and proportional to the "
        "stated intent:** propose the smallest end-to-end proof needed for "
        "the outcome and any stated acceptance or safety boundary. Do not "
        "add an adjacent workflow, cleanup, generalization, or future "
        "capability merely because it would be useful. "
        "**Smallest proof first, before decomposition.** Start from one "
        "concrete end-to-end path that proves the requested outcome using "
        "existing commands, owners and platform behavior. For each proposed "
        "new abstraction, process boundary, persisted record, lifecycle or "
        "configuration surface, name the current requirement that fails "
        "without it and the concrete reason unchanged reuse or a direct "
        "call cannot satisfy that requirement. Possible future reuse, "
        "symmetry, generic robustness and internal consistency are not "
        "reasons to add it. If evidence is missing, keep the uncertainty "
        "explicit; do not design a framework around an assumed limitation. "
        "Preserve required safety, compatibility, authority and audit "
        "properties and explicit owner choices. When those choices prevent "
        "a smaller proof, surface the scope tradeoff rather than silently "
        "dropping them. Express the chosen proof and necessary departures "
        "through the existing step descriptions; add no new response "
        "fields or mandatory review artifact. "
        f"{_MECHANISM_REACH_RULE} Keep the step list "
        "at plan altitude: state observable outcomes, ownership, ordering, "
        "and acceptance boundaries; leave inner implementation choices to "
        "detail unless their exact behavior is itself a stated contract. "
        "Preserve assigned production, update, and consumer-integration work; "
        "checking supplied data does not implement the operation that supplies it. "
        "When a named prerequisite is not implemented yet, retain this plan's "
        "implementation steps conditional on that prerequisite. Do not replace "
        "an implementation outcome with only prerequisite verification, invent "
        "the missing prerequisite's interface, or implement its scope here.\n\n"
        "1. Use Glob/Read to confirm every path you plan to touch. Put "
        "paths to **existing** files the step modifies in `files:`, and "
        "paths to **new** files the step will create in `creates:`. A "
        "`files:` entry must already be on disk (a missing parent dir is "
        "flagged as a broken path); a `creates:` entry is expected to be "
        "absent and is exempt from that check, so use it for every new "
        "file rather than leaving invented paths in `files:`. **Always "
        "write the full path from the repo root** (e.g. "
        "`amplify/bedrock/chat-agent/agent.py`, not `chat-agent/agent.py` "
        "or a bare `agent.py`) — partial or basename-only paths get "
        "flagged downstream as stale/typo references. Reflect "
        "new-vs-existing in the complexity rating.\n"
        "2. Use Grep to look for symbols implied by the step descriptions. If "
        "the work is already partially done, rewrite the step description to "
        "reflect what's left (\"Replace X with Y\" instead of \"Add Y\") "
        "and shrink the complexity accordingly. If a step is fully done, "
        "drop it from the response.\n"
        "3. Note runtime dependencies the description implies (packages, "
        "SDKs, env vars) but which aren't already declared in "
        "`package.json` / `pyproject.toml` / equivalent. Fold any "
        "dependency-adding work into the relevant step description rather than "
        "leaving it implicit.\n"
        "4. Include a step (or fold into an existing step) for **test "
        "coverage**. Unit tests by default; integration tests ONLY "
        "for cross-module wiring (CLI entry points, orchestrators, "
        "end-to-end pipelines). Use the project's existing convention "
        "for marking the two tiers -- check `TESTING.md` at the repo "
        "root if it exists, otherwise pattern-match on how existing "
        "tests in the codebase are organized (pytest markers, file "
        "naming, build tags, etc.). Don't propose a step that ships "
        "untested behavior.\n"
        "5. Apply any rules from the accumulated lessons block below "
        "that fit this plan's surface. The lessons are authoritative "
        "context from prior runs — let them shape your file-path "
        "verification, your complexity estimates, and the way you "
        "decompose work.\n"
        "6. Classify every step's `change_type` in two stages, and add "
        "a one-line `rationale` defending the classification:\n"
        "   - **Stage 1 — code vs non-code.** A step that changes **no "
        "production code** (documentation, configuration, CI/workflow "
        "YAML, IaC / deploy wiring) is `non-code`. Doc or config edits "
        "that merely *accompany* a code change do NOT make the step "
        "non-code — touching production code is the discriminator.\n"
        "   - **Stage 2 — type-pure decomposition (code steps only).** "
        "The step's **code** must be as purely `refactor` "
        "(behavior-preserving restructuring) or purely `feature` (new "
        "behavior) as possible. When candidate code work mixes the two, "
        "**split it into separate `refactor` and `feature` steps joined "
        "by a `depends_on` edge** — conventionally refactor-then-feature "
        "(make the change easy, then make the easy change) — rather than "
        "emitting one mixed step. Non-code elements (doc updates, config) "
        "riding alongside a code step do NOT count as mixing and need no "
        "split.\n"
        "   - **Stage 3 — one concern per step (beyond type-purity).** "
        "For `feature` work, even when two pieces of work share a "
        "`change_type`, split them when they are distinct concerns: "
        "different control-flow shapes, or the same contract/guard "
        "restated across two loops or modules. A cross-cutting invariant "
        "re-implemented per call site is its own step. "
        f"{_REFACTOR_BOUNDARY_RULE} "
        "For either code type, a branch with no namable live scenario is "
        "NOT a step — "
        "defer it, don't harden it. Counterweight — do NOT over-fragment: "
        "count concerns, not steps; a step with no standalone acceptance "
        "criteria has been split too far.\n"
        "   - Each `rationale` is one line explaining why the step's code "
        "is purely refactor, purely feature, or why it carries no "
        "production code.\n"
        f"7. {_PROPOSAL_INTENT_ITEM}\n"
        f"8. {_PROPOSAL_DESTRUCTIVE_ITEM}\n"
        f"{tail_items}"
        + _STEP_PROPOSAL_RESPONSE_CONTRACT.render_prompt_block()
        + "\n\n"
        "`complexity` is `low` / `medium` / `high`, or omit/null when "
        "unknown. `files` is existing files modified, "
        "`creates` is new files the step adds (omit or use `[]` when the "
        f"step creates nothing). {depends_on_notes_explainer}"
        "`intent` is item 7's "
        "one-line why and is required on every entry. A mixed code step must "
        "appear as **two array entries linked by `depends_on`**, not one "
        "entry with a hedged `change_type`. Ids are assigned "
        "by the caller, 1-based on this response's array order — never "
        "invent or reuse an id from an earlier run. **`depends_on` entries "
        "are JSON integers** (`1`, `2`, …), never quoted strings. "
        "`depends_on_notes` keys denote the same integers but, "
        "like every JSON object key, are written as strings (`\"1\"`) — "
        "only the array items must be bare numbers. "
        "**Write every `description` in plain, everyday words** "
        "— name the change the way you'd say it to a teammate (\"Add "
        "worktree path helpers\"), not in dense or clever phrasing; keep "
        "real identifiers (file, function, flag names) but drop "
        "decorative vocabulary. Do not include the audit narrative in the "
        "response — fold every finding into step shapes. Trailing prose "
        "after the closing `]` is tolerated by the parser but adds no "
        "value."
        f"{lessons_section}"
        f"{project_context_section}"
        f"\n\nPlan description:\n{description}\n"
    )


def _render_sweep_context(steps: list[Step], description: str = "") -> str:
    """Render the focused property and proposed steps for the split sweep.

    The sweep needs both to classify reach rather than infer it from paths.
    """
    lines = [
        "Focused plan description:",
        description.strip() or "_not supplied_",
        "",
        "Proposed steps for this plan:",
        "",
        f"Create refactor boundary rule: {_REFACTOR_BOUNDARY_RULE}",
        "",
    ]
    for step in steps:
        files = ", ".join(step.files) if step.files else "(none)"
        creates = ", ".join(step.creates) if step.creates else "(none)"
        lines.append(f"- step {step.id}: {step.title}")
        lines.append("    declared boundary:")
        lines.append(f"      files: {files}")
        lines.append(f"      creates: {creates}")
    return "\n".join(lines)


@dataclass(frozen=True)
class Reference:
    """Developer / API documentation pointer rendered into the plan body.

    Sourced from claude's web research at create time. ``description`` is
    a one-line gloss naming what the reference covers; empty when claude
    omitted it (the bullet still renders, just without the trailing prose).
    """

    title: str
    url: str
    description: str = ""


@dataclass(frozen=True)
class ReferenceResearchResult:
    """The validated outcome of generic developer-document research."""

    outcome: Literal["populated", "empty", "unparseable"]
    references: tuple[Reference, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in {"populated", "empty", "unparseable"}:
            raise ValueError(f"unknown reference research outcome {self.outcome!r}")
        if self.outcome == "populated" and not self.references:
            raise ValueError("a populated reference result needs references")
        if self.outcome in {"empty", "unparseable"} and self.references:
            raise ValueError(f"a {self.outcome} reference result cannot carry references")

    @classmethod
    def from_references(cls, references: list[Reference]) -> "ReferenceResearchResult":
        """Classify retained parser entries as populated or deliberately empty."""
        retained = tuple(references)
        return cls("populated", retained) if retained else cls("empty")

    @classmethod
    def unparseable(cls) -> "ReferenceResearchResult":
        """Represent a response that does not satisfy the JSON-array contract."""
        return cls("unparseable")


@dataclass(frozen=True)
class _LocalCodeAnchor:
    """One inline Architecture anchor eligible for local-code grounding."""

    mention: str
    symbol: str
    path: Optional[Path] = None
    requires_symbol: bool = True


@dataclass(frozen=True)
class _LocalCodeGrounding:
    """Prompt context and durable citations for resolved Architecture code."""

    context: str
    resolved_anchors: tuple[str, ...]


_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_SYMBOLIC_ANCHOR_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*$"
)
_PATH_ANCHOR_RE = re.compile(
    r"^(?P<path>[A-Za-z0-9_./-]+\.[A-Za-z0-9_+-]+)(?::(?P<symbol>[A-Za-z_][A-Za-z0-9_.]*))?$"
)
_LOCAL_CODE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".mjs",
        ".py",
        ".rb",
        ".rs",
        ".swift",
        ".ts",
        ".tsx",
    }
)
_LOCAL_CODE_SKIP_DIRS = frozenset(
    {
        ".git",
        ".plan-tool",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "target",
        "third_party",
        "vendor",
    }
)
_LOCAL_CODE_EXCERPT_BYTES = 3_000
_LOCAL_CODE_MAX_FILE_BYTES = 1_000_000
_LOCAL_CODE_AMBIGUOUS_PATHS = 8


def _architecture_code_anchors(source_text: str) -> list[_LocalCodeAnchor]:
    """Extract explicit code anchors from the seed's ``## Architecture`` only.

    Inline code is the seed author's opt-in to a repository lookup. Restricting
    the pass to that section and to these anchors keeps create from becoming an
    open-ended code review of prose that merely resembles an identifier.
    """
    architecture = extract_h2_sections(
        _strip_frontmatter(source_text), strip_fenced_code=True
    ).get("architecture", "")
    out: list[_LocalCodeAnchor] = []
    seen: set[str] = set()
    for match in _INLINE_CODE_RE.finditer(architecture):
        mention = match.group(1).strip().removesuffix("()")
        path_match = _PATH_ANCHOR_RE.fullmatch(mention)
        if path_match is not None:
            path = Path(path_match.group("path"))
            declared_symbol = path_match.group("symbol")
            symbol = (declared_symbol or path.stem).rsplit(".", 1)[-1]
            anchor = _LocalCodeAnchor(
                mention=mention,
                symbol=symbol,
                path=path,
                requires_symbol=declared_symbol is not None,
            )
        elif _SYMBOLIC_ANCHOR_RE.fullmatch(mention):
            anchor = _LocalCodeAnchor(
                mention=mention,
                symbol=re.split(r"[.:]", mention)[-1],
            )
        else:
            continue
        key = anchor.mention.lower()
        if key not in seen:
            seen.add(key)
            out.append(anchor)
    # A ``path:symbol`` anchor is the seed's unambiguous choice for a symbol.
    # Do not also broad-scan a matching bare spelling: doing so could invent an
    # ambiguity after the seed already supplied the precise target.
    explicit_symbols = {
        anchor.symbol
        for anchor in out
        if anchor.path is not None and anchor.requires_symbol
    }
    return [
        anchor
        for anchor in out
        if anchor.path is not None or anchor.symbol not in explicit_symbols
    ]


def _iter_local_code_files(repo_root: Path) -> list[Path]:
    """Return source files that can satisfy a seed's explicit code anchor."""
    paths: list[Path] = []
    try:
        for directory, dirnames, filenames in repo_root.walk():
            dirnames[:] = [
                name for name in dirnames if name not in _LOCAL_CODE_SKIP_DIRS
            ]
            paths.extend(
                directory / name
                for name in filenames
                if (directory / name).suffix.lower() in _LOCAL_CODE_SUFFIXES
            )
    except OSError:
        return []
    return sorted(paths, key=lambda path: path.relative_to(repo_root).as_posix())


def _read_local_code_file(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Read one bounded source file, returning an explanatory miss on failure."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if size > _LOCAL_CODE_MAX_FILE_BYTES:
        return None, (
            f"too large for local grounding ({size} bytes; limit "
            f"{_LOCAL_CODE_MAX_FILE_BYTES})"
        )
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, f"unreadable: {exc}"


def _declares_local_symbol(text: str, symbol: str) -> bool:
    """Recognize declaration shapes without treating comments or calls as code."""
    escaped = re.escape(symbol)
    patterns = (
        rf"(?m)^[ \t]*(?:async[ \t]+)?def[ \t]+{escaped}\b",
        rf"(?m)^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?"
        rf"(?:async[ \t]+)?(?:function|func|fn|class|interface|type|struct|enum|trait)"
        rf"[ \t]+{escaped}\b",
        rf"(?m)^[ \t]*func(?:[ \t]+\([^\n)]*\))?[ \t]+{escaped}\b",
        rf"(?m)^[ \t]*(?:export|pub|static|public|private|protected|final|const|let|var)"
        rf"[ \t]+{escaped}\b",
        rf"(?m)^[ \t]*(?:public|private|protected|static|final|virtual|override|inline|extern)"
        rf"(?:[ \t]+[A-Za-z_][A-Za-z0-9_:<>,\[\]&*]*)+[ \t]+{escaped}"
        rf"[ \t]*\([^;\n]*\)[ \t]*(?:\{{|=>)",
    )
    if symbol.isupper():
        patterns += (rf"(?m)^[ \t]*{escaped}[ \t]*=",)
    return any(re.search(pattern, text) is not None for pattern in patterns)


def _render_local_code_grounding(
    source_text: str, repo_root: Path
) -> _LocalCodeGrounding:
    """Resolve Architecture anchors once, surfacing ambiguity instead of guessing.

    Bare symbols are accepted only when one repository source file declares
    them. Multiple declarations are named as an ambiguity rather than silently
    selecting an alphabetically-first look-alike. Each source file is read at
    most once per synthesis attempt, with generated/vendor trees and oversized
    files excluded from the broad scan.
    """
    root = repo_root.resolve()
    anchors = _architecture_code_anchors(source_text)
    texts: dict[Path, tuple[Optional[str], Optional[str]]] = {}

    def read(path: Path) -> tuple[Optional[str], Optional[str]]:
        if path not in texts:
            texts[path] = _read_local_code_file(path)
        return texts[path]

    matches: dict[_LocalCodeAnchor, list[Path]] = {anchor: [] for anchor in anchors}
    misses: dict[_LocalCodeAnchor, str] = {}
    bare_anchors = [anchor for anchor in anchors if anchor.path is None]
    for anchor in anchors:
        if anchor.path is None:
            continue
        path = (root / anchor.path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            misses[anchor] = "the named repository path is not on disk"
            continue
        text, reason = read(path)
        if text is None:
            misses[anchor] = reason or "the named repository source is unavailable"
        elif anchor.requires_symbol and not _declares_local_symbol(text, anchor.symbol):
            misses[anchor] = "the named source does not declare that symbol"
        else:
            matches[anchor].append(path)

    if bare_anchors:
        for path in _iter_local_code_files(root):
            text, _ = read(path)
            if text is None:
                continue
            for anchor in bare_anchors:
                if _declares_local_symbol(text, anchor.symbol):
                    matches[anchor].append(path)

    blocks: list[str] = []
    resolved_anchors: list[str] = []
    for anchor in anchors:
        paths = sorted(
            matches[anchor], key=lambda path: path.relative_to(root).as_posix()
        )
        if not paths:
            blocks.append(
                f"### `{anchor.mention}` _(no resolved repository declaration)_\n\n"
                f"{misses.get(anchor, 'This may name new code; absence alone is not a conflict.')}"
            )
            continue
        if len(paths) > 1:
            labels = [
                f"`{path.relative_to(root).as_posix()}:{anchor.symbol}`"
                for path in paths[:_LOCAL_CODE_AMBIGUOUS_PATHS]
            ]
            remaining = len(paths) - len(labels)
            suffix = f"; and {remaining} more" if remaining else ""
            blocks.append(
                f"### `{anchor.mention}` _(ambiguous repository declaration)_\n\n"
                "Do not select a look-alike as evidence. The seed must name one "
                f"explicit `path:symbol` anchor: {', '.join(labels)}{suffix}."
            )
            continue
        path = paths[0]
        text, reason = read(path)
        if text is None:
            blocks.append(
                f"### `{anchor.mention}` _(unavailable repository source)_\n\n"
                f"{reason or 'No source text was available.'}"
            )
            continue
        rel = path.relative_to(root).as_posix()
        citation = f"{rel}:{anchor.symbol}" if anchor.requires_symbol else rel
        excerpt = build_prompt_excerpt(
            rel,
            text,
            [anchor.symbol],
            max_bytes=_LOCAL_CODE_EXCERPT_BYTES,
        )
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        blocks.append(
            f"### `{anchor.mention}` — `{citation}`\n\n"
            f"_Source fingerprint: `{fingerprint}`_\n\n"
            f"```\n{excerpt.text}\n```"
        )
        if anchor.requires_symbol:
            resolved_anchors.append(citation)
    return _LocalCodeGrounding(
        context="\n\n".join(blocks),
        resolved_anchors=tuple(resolved_anchors),
    )


def _render_local_code_context(source_text: str, repo_root: Path) -> str:
    """Compatibility wrapper for callers that need only the prompt block."""
    return _render_local_code_grounding(source_text, repo_root).context


def _step_declared_code_files(step: Step) -> frozenset[str]:
    """A step's declared *production* source-code files, for cohesion checks.

    ``tests/`` paths are excluded: two otherwise-unrelated steps routinely
    touch the same test module by convention, so a shared test file is weak
    cohesion evidence, while a shared production file is the strongest
    structural signal a plan's frontmatter carries that two steps are
    actually coupled.
    """
    return frozenset(
        f
        for f in step.all_files
        if Path(f).suffix.lower() in _LOCAL_CODE_SUFFIXES and not f.startswith("tests/")
    )


@dataclass(frozen=True)
class _BridgingDependencyEdge:
    """A ``depends_on`` edge whose two steps share no declared production file."""

    dependent_id: int
    antecedent_id: int
    dependent_files: tuple[str, ...]
    antecedent_files: tuple[str, ...]


def _bridging_dependency_edges(steps: list[Step]) -> list[_BridgingDependencyEdge]:
    """``depends_on`` edges with no shared declared production file.

    A shared production file is the only structural evidence a plan's
    frontmatter carries that two steps are actually coupled — nothing else
    backs a dependency claim. An edge where either side declares no
    production file has nothing to compare and is excluded, not flagged (a
    docs-only or test-only step is not "unjustified", it simply has no
    footprint to check). Deterministic: a pure frontmatter comparison, no
    Claude call and no new judgment — see BACKLOG #252.
    """
    code_files = {step.id: _step_declared_code_files(step) for step in steps}
    edges: list[_BridgingDependencyEdge] = []
    for step in steps:
        dependent_files = code_files[step.id]
        if not dependent_files:
            continue
        for antecedent_id in step.depends_on:
            antecedent_files = code_files.get(antecedent_id)
            if not antecedent_files:
                continue
            if dependent_files.isdisjoint(antecedent_files):
                edges.append(
                    _BridgingDependencyEdge(
                        dependent_id=step.id,
                        antecedent_id=antecedent_id,
                        dependent_files=tuple(sorted(dependent_files)),
                        antecedent_files=tuple(sorted(antecedent_files)),
                    )
                )
    edges.sort(key=lambda e: (e.dependent_id, e.antecedent_id))
    return edges


def _render_dependency_cohesion_block(edges: list[_BridgingDependencyEdge]) -> str:
    """Render bridging ``depends_on`` edges as the claims most worth verifying.

    Purely informational — an ordering/emphasis hint, never a verdict. Empty
    string when there are none, matching the other grounding blocks'
    empty-evidence convention (the caller supplies the no-evidence note).
    """
    lines = [
        f"- Step {edge.dependent_id} depends on step {edge.antecedent_id} — "
        "declares no file in common (step "
        f"{edge.dependent_id}: {', '.join(f'`{f}`' for f in edge.dependent_files)}; "
        f"step {edge.antecedent_id}: "
        f"{', '.join(f'`{f}`' for f in edge.antecedent_files)})."
        for edge in edges
    ]
    return "\n".join(lines)


def _render_references_prompt(plan_title: str, description: str) -> str:
    """Build the web-research prompt fed to claude for ``References`` content.

    Asks for official vendor docs and primary API references rather than
    blogs / tutorials / Stack Overflow — these are the surfaces an
    implementer will repeatedly consult, and they age better than
    secondary write-ups. The strict JSON-only contract mirrors
    :func:`_render_from_prompt` so parsing stays uniform; the explicit
    "empty array" instruction tells claude how to signal "couldn't find
    anything" instead of inventing references.
    """
    return (
        "Search the web for authoritative developer and API reference "
        "documentation that an engineer would consult while implementing "
        f'the plan titled "{plan_title}".\n\n'
        "Focus on official vendor documentation (e.g. AWS service docs, "
        "Anthropic docs, framework docs), primary API references, RFCs, "
        "and well-maintained library guides. Skip blog posts, marketing "
        "pages, tutorials, and Q&A threads.\n\n"
        + _REFERENCE_RESPONSE_CONTRACT.render_prompt_block()
        + "\n\nReturn 3-7 "
        "entries when good references exist. Each description should be "
        "one short sentence naming what the reference covers and why an "
        "implementer would open it. If you cannot find suitable "
        "references, return an empty array [].\n\n"
        f"Plan description:\n{description}\n"
    )


def _render_references_repair_prompt(prompt: str, rejected_response: str) -> str:
    """Ask for one replacement response after generic research fails to parse."""
    return (
        prompt
        + "\n\n## Repair\n\nYour previous response was rejected because it "
        "did not satisfy the required JSON-array response format. Return a "
        "replacement response; do not merge or reuse entries from the rejected "
        "response.\n\nPrevious response:\n\n"
        + rejected_response
        + "\n\n"
        + _REFERENCE_RESPONSE_CONTRACT.render_prompt_block()
        + "\n"
    )


def _render_roadmap_references_prompt(
    targets: tuple[RoadmapResearchTarget, ...],
) -> str:
    """Render the public portion of a selected roadmap research request."""
    request_rows = [
        {"token": target.token, "product": target.product}
        for target in targets
    ]
    return (
        "Search the web for authoritative developer and API reference "
        "documentation for each recorded product below. Focus on official "
        "vendor documentation, primary API references, RFCs, and "
        "well-maintained library guides. Skip blog posts, marketing pages, "
        "tutorials, and Q&A threads.\n\n"
        "Return exactly one result for every requested token and no result "
        "for any other token. Each result's `references` value must be an "
        "array of valid references, or the explicit empty array [] when no "
        "suitable source exists.\n\n"
        "Requested products:\n"
        + json.dumps(request_rows, indent=2, ensure_ascii=False)
        + "\n\n"
        + _ROADMAP_REFERENCE_RESPONSE_CONTRACT.render_prompt_block()
        + "\n"
    )


def _parse_references_json(raw: str) -> ReferenceResearchResult:
    """Extract a typed generic research result from claude's response.

    Tolerates leading / trailing chatter the way :func:`_parse_steps_json`
    does — finds the outermost ``[`` / ``]`` and parses what's between.
    Entries missing an http(s) URL or a non-empty title are silently
    dropped (claude occasionally emits placeholder rows); the result is
    populated when entries survive and empty when the parseable array retains
    none. JSON-level failure or a non-array root produces an unparseable
    result, which callers keep distinct from deliberate emptiness.
    """
    items = _REFERENCE_RESPONSE_CONTRACT.decode(raw)
    if not isinstance(items, list):
        return ReferenceResearchResult.unparseable()
    refs: list[Reference] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        desc = item.get("description", "")
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(desc, str):
            desc = ""
        refs.append(
            Reference(
                title=title.strip(),
                url=url,
                description=desc.strip(),
            )
        )
    return ReferenceResearchResult.from_references(refs)


def _parse_roadmap_reference(
    item: object, *, target_token: str, index: int
) -> Reference:
    """Decode one product-mode reference without the generic drop policy."""
    if not isinstance(item, dict) or set(item) - {"title", "url", "description"}:
        raise CreateError(
            "research protocol failure: "
            f"target {target_token!r} reference {index} is not a valid Reference"
        )
    title = item.get("title")
    url = item.get("url")
    description = item.get("description", "")
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(url, str)
        or not url.strip().startswith(("http://", "https://"))
        or not isinstance(description, str)
    ):
        raise CreateError(
            "research protocol failure: "
            f"target {target_token!r} reference {index} is not a valid Reference"
        )
    return Reference(
        title=title.strip(),
        url=url.strip(),
        description=description.strip(),
    )


def _parse_roadmap_references_json(
    raw: str,
    targets: tuple[RoadmapResearchTarget, ...],
) -> tuple[RoadmapResearchVerdict, ...]:
    """Require a complete one-to-one source result for external targets."""
    records = _ROADMAP_REFERENCE_RESPONSE_CONTRACT.decode(
        raw, allow_surrounding=False
    )
    if not isinstance(records, list):
        raise CreateError(
            "research protocol failure: product research must return one JSON array"
        )

    expected_tokens = {target.token for target in targets}
    verdicts: dict[str, RoadmapResearchVerdict] = {}
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or set(record) != {"token", "references"}:
            raise CreateError(
                "research protocol failure: "
                f"product result {index} must contain only token and references"
            )
        token = record["token"]
        sources = record["references"]
        if not isinstance(token, str) or not token.strip():
            raise CreateError(
                f"research protocol failure: product result {index} has no valid token"
            )
        if token not in expected_tokens:
            raise CreateError(
                f"research protocol failure: received foreign target {token!r}"
            )
        if token in verdicts:
            raise CreateError(
                f"research protocol failure: received duplicate target {token!r}"
            )
        if not isinstance(sources, list):
            raise CreateError(
                "research protocol failure: "
                f"target {token!r} references must be an array"
            )
        references = tuple(
            _parse_roadmap_reference(source, target_token=token, index=source_index)
            for source_index, source in enumerate(sources, start=1)
        )
        verdicts[token] = RoadmapResearchVerdict(
            target_token=token,
            references=references,
            source="external",
        )

    missing_tokens = [target.token for target in targets if target.token not in verdicts]
    if missing_tokens:
        raise CreateError(
            "research protocol failure: missing result for target "
            + ", ".join(repr(token) for token in missing_tokens)
        )
    return tuple(verdicts[target.token] for target in targets)


def _local_roadmap_research_verdicts(
    targets: tuple[RoadmapResearchTarget, ...],
) -> tuple[RoadmapResearchVerdict, ...]:
    """Derive local no-source verdicts after enforcing their fallback text."""
    verdicts: list[RoadmapResearchVerdict] = []
    for target in targets:
        if target.research_disclosure == ResearchDisclosure.EXTERNAL:
            continue
        if target.description is None or not target.description.strip():
            raise CreateError(
                f"local roadmap product at {target.origin} has no description; "
                "add a description or mark research_disclosure: external"
            )
        verdicts.append(
            RoadmapResearchVerdict(
                target_token=target.token,
                references=(),
                source="local",
            )
        )
    return tuple(verdicts)


def _load_roadmap_research_targets(
    location: TrackedSeedLocation,
) -> tuple[RoadmapResearchTarget, ...]:
    """Snapshot product rows from the accepted version in source order."""
    roadmap_root = location.state_path.parent
    plans_dir = roadmap_root.parent.parent
    slug = location.roadmap_slug
    try:
        accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    except RoadmapVersionError as exc:
        raise CreateError(f"could not load the accepted roadmap version for '{slug}': {exc}") from exc
    if accepted is None:
        raise NoPublishedRoadmapVersionError(no_published_version_message(plans_dir, slug))
    members = dict(zip(VERSION_ARTIFACT_KEYS, accepted.artifact_bytes, strict=True))
    try:
        constraints = parse_constraints_artifact(members["constraints"].decode("utf-8"))
        components = parse_components_artifact(members["components"].decode("utf-8"))
    except (RoadmapArtifactError, ValueError) as exc:
        raise CreateError(
            f"could not load selected roadmap products for '{slug}': {exc}"
        ) from exc

    targets: list[RoadmapResearchTarget] = []
    for artifact_name, collection, rows in (
        ("02-constraints.md", "hosting", constraints.hosting),
        ("03-components.md", "stores", components.stores),
    ):
        for position, row in enumerate(rows, start=1):
            product = (row.product or "").strip()
            if not product:
                continue
            targets.append(
                RoadmapResearchTarget(
                    token=f"{collection}-{position}",
                    product=product,
                    origin=(
                        f"{artifact_name} {collection} row {position} "
                        f"(id {row.id!r})"
                    ),
                    description=row.description,
                    research_disclosure=row.research_disclosure,
                )
            )
    return tuple(targets)


def _build_research_context(title: str, steps: list[Step]) -> str:
    """Construct a research description from title + step titles.

    Used on the interactive create path, where the wizard has no
    ``--from`` description to forward. Step files are included when
    present so claude can ground its search on the specific frameworks
    / packages the implementer will be touching, rather than guessing
    from the title alone.
    """
    parts: list[str] = [f"Title: {title}", "", "Planned steps:"]
    for s in steps:
        parts.append(f"- {s.title}")
        if s.all_files:
            parts.append(f"  files: {', '.join(s.all_files)}")
    return "\n".join(parts)


def _invoke_or_fail(
    fn: Callable[[], str],
    *,
    handle: Any,
    run_logger: Optional[RunLoggerLike],
    phase: str,
    attempt: int,
    start: float,
    base_elapsed: float = 0.0,
) -> str:
    """Run one create-phase invoker call, closing the progress handle and
    recording a ``transport`` attempt-failure (matching the codebase's
    existing failure-kind vocabulary for a raised invoker exception, as
    opposed to ``"parse"`` for a bad-but-returned response) before
    re-raising, instead of letting the exception escape unclosed.
    """
    try:
        return fn()
    except Exception as exc:
        elapsed = base_elapsed + (time.monotonic() - start)
        handle.fail(elapsed, f"claude invocation failed: {exc}")
        if run_logger is not None:
            run_logger.attempt_failed(
                phase=phase, attempt=attempt, failure_kind="transport"
            )
        raise


def propose_references_from_claude(
    plan_title: str,
    description: str,
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
    iteration: int = 0,
) -> ReferenceResearchResult:
    """Ask claude to web-search for dev / API reference docs.

    Returns a typed result that distinguishes unparseable output from a valid
    empty array while preserving the retained ``Reference`` entries. A live
    unparseable reply gets one replacement request; cached responses do not.
    Progress is surfaced through the same reporter pattern as
    :func:`propose_steps_from_claude` so the user sees a closing line on
    stderr instead of silent hang during the web research round-trip.

    When ``slug``, ``output_dir``, and ``repo_root`` are all provided the
    response is memoized under
    ``.plan-tool/checkpoints/<slug>/create-references.json``. A hit on a
    checkpoint whose ``input_hash`` matches slug + plan_title + description
    + output dir returns the cached raw response without invoking claude.
    ``resume=False`` skips the load but still saves on success — so a
    ``--no-resume`` run primes the cache for the next run. Tests that omit
    ``slug`` / ``output_dir`` get the historical no-checkpoint behavior.
    """
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    prompt = _render_references_prompt(plan_title, description)

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _references_input_hash(
            slug,
            plan_title,
            description,
            output_dir,
            repo_root,
            iteration=iteration,
        )
        ckpt_name = (
            _REFERENCES_CHECKPOINT_NAME
            if iteration == 0
            else f"{_REFERENCES_CHECKPOINT_NAME}-iter{iteration}"
        )
        ckpt_path = checkpoint_path(repo_root, slug, ckpt_name)

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if (
        cached is not None
        and run_logger is not None
        and input_hash is not None
    ):
        run_logger.checkpoint_hit(
            _REFERENCES_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached references research (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _REFERENCES_CHECKPOINT_NAME, "force"
                )
            cached = None

    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Researching developer docs (resumed from checkpoint)"
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        prompt_bytes = len(prompt.encode("utf-8"))
        if run_logger is not None:
            run_logger.install_call_end_sink(
                phase="propose_references", attempt=1
            )
        try:
            handle = reporter.start_step(
                1, 1, "Researching developer docs",
                phase="propose_references",
                attempt=1,
                prompt_bytes=prompt_bytes,
                prompt_sha256=hash_prompt(prompt),
            )
            start = time.monotonic()
            raw = _invoke_or_fail(
                lambda: invoker(prompt),
                handle=handle,
                run_logger=run_logger,
                phase="propose_references",
                attempt=1,
                start=start,
            )
            elapsed = time.monotonic() - start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()

    result = _parse_references_json(raw)
    if result.outcome == "unparseable" and cached is None:
        if run_logger is not None:
            run_logger.attempt_failed(
                phase="propose_references", attempt=1, failure_kind="parse"
            )
        handle.notice(
            "developer-doc research: first response was unparseable; retrying once",
            kind="retry",
        )
        repair_prompt = _render_references_repair_prompt(prompt, raw)
        repair_prompt_bytes = len(repair_prompt.encode("utf-8"))
        if run_logger is not None:
            run_logger.claude_call_start(
                phase="propose_references",
                attempt=2,
                prompt_bytes=repair_prompt_bytes,
                prompt_sha256=hash_prompt(repair_prompt),
            )
            run_logger.install_call_end_sink(
                phase="propose_references", attempt=2
            )
        # The repair embeds the full rejected response, so measure its own
        # prompt and suppress the generic backstop only when that succeeds.
        repair_covered = _maybe_warn_create_budget(
            total_bytes=repair_prompt_bytes,
            blocks=[("rejected-response", len(raw.encode("utf-8")))],
            phase="create-references",
            surface="create developer-document research",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        try:
            retry_start = time.monotonic()

            def _do_repair_call() -> str:
                with suppress_prompt_budget_backstop(active=repair_covered):
                    return invoker(repair_prompt)

            raw = _invoke_or_fail(
                _do_repair_call,
                handle=handle,
                run_logger=run_logger,
                phase="propose_references",
                attempt=2,
                start=retry_start,
                base_elapsed=elapsed,
            )
            elapsed += time.monotonic() - retry_start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()
        result = _parse_references_json(raw)
        if result.outcome == "unparseable":
            if run_logger is not None:
                run_logger.attempt_failed(
                    phase="propose_references", attempt=2, failure_kind="parse"
                )
            dump = _dump_failed_response(
                repo_root=repo_root,
                slug=slug,
                phase="propose_references",
                iteration=iteration,
                raw=raw,
            )
            hint = (
                f" (raw response saved to {dump.relative_to(repo_root)})"
                if dump is not None and repo_root is not None
                else ""
            )
            handle.fail(elapsed, f"claude returned an unparseable response{hint}")
            if run_logger is not None and dump is not None and repo_root is not None:
                run_logger.parse_failure(
                    phase="propose_references",
                    attempt=2,
                    failure_path=str(dump.relative_to(repo_root)),
                    reason="unparseable_references_json",
                    iteration=iteration,
                )
            return result

    if result.outcome == "unparseable":
        handle.fail(elapsed, "claude returned an unparseable response")
        return result

    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save references checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _REFERENCES_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )

    handle.complete(elapsed, len(raw.encode("utf-8")))
    return result


def propose_roadmap_references_from_claude(
    targets: tuple[RoadmapResearchTarget, ...],
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> tuple[RoadmapResearchVerdict, ...]:
    """Collect strict source verdicts for one selected roadmap snapshot."""
    local_verdicts = _local_roadmap_research_verdicts(targets)
    external_targets = tuple(
        target
        for target in targets
        if target.research_disclosure == ResearchDisclosure.EXTERNAL
    )
    if not external_targets:
        return local_verdicts

    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    prompt = _render_roadmap_references_prompt(external_targets)

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _references_input_hash(
            slug,
            "",
            "",
            output_dir,
            repo_root,
            roadmap_targets=targets,
        )
        ckpt_path = checkpoint_path(repo_root, slug, _REFERENCES_CHECKPOINT_NAME)

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if cached is not None and run_logger is not None and input_hash is not None:
        run_logger.checkpoint_hit(
            _REFERENCES_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached product references research (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(_REFERENCES_CHECKPOINT_NAME, "force")
            cached = None

    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Researching recorded product docs (resumed from checkpoint)"
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        prompt_bytes = len(prompt.encode("utf-8"))
        if run_logger is not None:
            run_logger.install_call_end_sink(
                phase="propose_references", attempt=1
            )
        try:
            handle = reporter.start_step(
                1, 1, "Researching recorded product docs",
                phase="propose_references",
                attempt=1,
                prompt_bytes=prompt_bytes,
                prompt_sha256=hash_prompt(prompt),
            )
            start = time.monotonic()
            raw = invoker(prompt)
            elapsed = time.monotonic() - start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()

    try:
        external_verdicts = _parse_roadmap_references_json(raw, external_targets)
    except CreateError as exc:
        handle.fail(elapsed, str(exc))
        raise

    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save references checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _REFERENCES_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )

    handle.complete(elapsed, len(raw.encode("utf-8")))
    by_token = {
        verdict.target_token: verdict
        for verdict in (*local_verdicts, *external_verdicts)
    }
    return tuple(by_token[target.token] for target in targets)


def _description_backed_disclosure(products: list[str]) -> str:
    """Name description-backed products publishing without a decoded source.

    Discloses the real, recorded justification honestly rather than
    inventing a citation for it — distinct from silence, which would drop
    that provenance from the published plan entirely.
    """
    deduped = list(dict.fromkeys(products))
    noun = "product" if len(deduped) == 1 else "products"
    verb = "publishes" if len(deduped) == 1 else "publish"
    named = ", ".join(deduped)
    return (
        f"The following selected {noun} {verb} under a recorded operator "
        f"description rather than a decoded source: {named}."
    )


def _selected_roadmap_references_for_publication(
    targets: tuple[RoadmapResearchTarget, ...],
    verdicts: tuple[RoadmapResearchVerdict, ...],
) -> tuple[list[Reference], Optional[str]]:
    """Return publishable selected references after checking each target."""
    if len(targets) != len(verdicts) or any(
        target.token != verdict.target_token
        for target, verdict in zip(targets, verdicts)
    ):
        raise CreateError(
            "roadmap research results do not match the selected product snapshot"
        )

    references: list[Reference] = []
    description_backed_products: list[str] = []
    for target, verdict in zip(targets, verdicts):
        references.extend(verdict.references)
        if verdict.references:
            continue
        if target.description is not None and target.description.strip():
            description_backed_products.append(target.product)
            continue
        raise CreateError(
            f"selected roadmap product {target.product!r} at {target.origin} "
            "has no source evidence or recorded description; add a description "
            "or repair source evidence before retrying"
        )

    if not references:
        return references, _ROADMAP_NO_SOURCE_REFERENCES_BODY
    if description_backed_products:
        body = _render_references_body(references)
        body += "\n\n" + _description_backed_disclosure(description_backed_products)
        return references, body
    return references, None


def gather_reference_docs(
    references: list[Reference],
    *,
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> list[FetchedDoc]:
    """Fetch the content of each reference URL, with checkpoint/resume.

    Wraps :func:`plan_tool.fetch.fetch_reference_docs` in the same
    checkpoint contract the claude round-trips use: when ``slug`` /
    ``output_dir`` / ``repo_root`` are all provided the fetched docs are
    memoized under ``.plan-tool/checkpoints/<slug>/create-reference-docs.json``
    keyed by the (ordered) reference URL set. A hit returns the cached
    docs without touching the network; ``resume=False`` skips the load but
    still saves so a ``--no-resume`` run primes the cache. Runs once per
    create (round 0) — no ``iteration`` shard, mirroring the distill pass.

    Returns the per-URL :class:`FetchedDoc` list (including ``error`` docs
    so the run log can explain misses). An empty ``references`` short-
    circuits to ``[]`` without a reporter step. Fetching never raises:
    :func:`plan_tool.fetch.fetch_url` funnels every failure into an
    ``error`` doc, so a dead link can't abort the create.
    """
    if not references:
        return []
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    urls = [r.url for r in references]

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _reference_docs_input_hash(
            slug, urls, output_dir, repo_root
        )
        ckpt_path = checkpoint_path(
            repo_root, slug, _REFERENCE_DOCS_CHECKPOINT_NAME
        )

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if (
        cached is not None
        and run_logger is not None
        and input_hash is not None
    ):
        run_logger.checkpoint_hit(
            _REFERENCE_DOCS_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached reference-doc fetch (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _REFERENCE_DOCS_CHECKPOINT_NAME, "force"
                )
            cached = None

    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Fetching reference docs (resumed from checkpoint)"
        )
        docs = docs_from_json(cached.payload)
        elapsed = 0.0
    else:
        handle = reporter.start_step(
            1, 1, f"Fetching {len(urls)} reference doc(s)"
        )
        start = time.monotonic()
        docs = fetch_reference_docs(urls)
        elapsed = time.monotonic() - start
        if ckpt_path is not None and input_hash is not None:
            try:
                save_checkpoint(
                    ckpt_path,
                    Checkpoint(
                        input_hash=input_hash,
                        payload=docs_to_json(docs),
                        created_at=datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat(),
                    ),
                )
            except OSError as exc:
                tool(
                    f"failed to save reference-docs checkpoint {ckpt_path} "
                    f"({exc}); resume on next run will re-fetch"
                )
            else:
                if run_logger is not None:
                    run_logger.checkpoint_save(
                        _REFERENCE_DOCS_CHECKPOINT_NAME,
                        input_hash,
                        len(docs_to_json(docs).encode("utf-8")),
                    )

    fetched_bytes = sum(
        len(d.text.encode("utf-8")) for d in docs if d.ok
    )
    handle.complete(elapsed, fetched_bytes)
    return docs


def _fetch_reference_docs_block(
    references: list[Reference],
    *,
    fetch_docs: bool,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> str:
    """Fetch reference docs and render the synthesis-prompt grounding block.

    Returns ``""`` (seed-only synthesis) when ``fetch_docs`` is off, there
    are no references, or nothing fetched successfully. Wraps the fetch in
    a ``fetch_reference_docs`` run-log phase whose outcome is ``ok`` when
    at least one doc produced text, ``skipped`` otherwise — matching how
    the references / body-sections phases report an empty result.
    """
    if not fetch_docs or not references:
        if run_logger is not None:
            run_logger.phase_start("fetch_reference_docs")
            run_logger.phase_end(
                "fetch_reference_docs",
                0,
                "skipped",
                skip_reason=(
                    "no_fetch_docs" if not fetch_docs else "no_references"
                ),
            )
        return ""

    if run_logger is not None:
        run_logger.phase_start("fetch_reference_docs")
    fetch_t0 = time.monotonic()
    outcome = "ok"
    try:
        docs = gather_reference_docs(
            references,
            slug=slug,
            output_dir=output_dir,
            repo_root=repo_root,
            resume=resume,
            input_fn=input_fn,
            run_logger=run_logger,
        )
        block = render_reference_docs_block(docs)
        if not block:
            outcome = "skipped"
        return block
    except Exception:
        outcome = "error"
        raise
    finally:
        if run_logger is not None:
            run_logger.phase_end(
                "fetch_reference_docs",
                int((time.monotonic() - fetch_t0) * 1000),
                outcome,
            )


def _canonical_body_section_keys() -> tuple[str, ...]:
    """Return the canonical key set the body-sections round-trip owns.

    Wrapper around :data:`_BODY_SECTIONS_CANONICAL_KEYS` exposed as a
    callable so tests can monkeypatch a smaller key set without
    mutating module state.
    """
    return _BODY_SECTIONS_CANONICAL_KEYS


def _render_section_shapes_block() -> str:
    """Build the ``${section_shapes_block}`` substitution for the prompt.

    Emits one bullet per canonical key: the key, its policy tag
    (``[derive from intent]`` vs ``[evidence-only]`` from
    :data:`_DERIVE_FROM_INTENT_SECTIONS`), and the shape gloss from
    :data:`PLAN_BODY_SECTION_SHAPES`. The tag is the single source of
    truth both the distill and synthesis prompts steer by. Keys that
    have no entry in the shapes map are skipped silently — the prompt
    still parses, just with one fewer guidance bullet.
    """
    lines: list[str] = []
    for section in _canonical_body_section_keys():
        shape = PLAN_BODY_SECTION_SHAPES.get(section)
        if not shape:
            continue
        policy = (
            "derive from intent"
            if section in _DERIVE_FROM_INTENT_SECTIONS
            else "evidence-only"
        )
        lines.append(f"- **{section}** _[{policy}]_ — {shape}")
    for section in _OPTIONAL_PLAN_BODY_SECTIONS:
        shape = OPTIONAL_PLAN_BODY_SECTION_SHAPES.get(section)
        if shape:
            lines.append(f"- **{section}** _[conditional]_ — {shape}")
    return "\n".join(lines)


def _render_reference_docs_section(reference_docs: str) -> str:
    """Build the ``${reference_docs_block}`` substitution for the prompt.

    ``reference_docs`` is the pre-rendered markdown from
    :func:`plan_tool.fetch.render_reference_docs_block` (empty when nothing
    was fetched). On the empty case the placeholder renders a one-line
    "none fetched" note so the prompt's "Reference documentation" heading
    isn't left dangling and Claude is told to fall back to the seed and any
    local repository evidence.
    """
    if not reference_docs.strip():
        return "_None fetched — use the seed and local repository evidence below._"
    return reference_docs


def _render_synthesis_prompt(
    source_text: str,
    *,
    reference_docs: str = "",
    local_code_context: str = "",
    local_code_anchors: tuple[str, ...] = (),
    dependency_cohesion_block: str = "",
    project_context: str = "",
    repair_error: Optional[str] = None,
    prior_response: Optional[str] = None,
) -> str:
    """Load ``prompts/synthesize-body.md`` and substitute the placeholders.

    On the initial call ``repair_block`` is the empty string. On the
    single repair retry, the block appends the prior response and the
    validation error so Claude can correct itself in one more turn.
    Mixed-argument cases (one of ``repair_error`` / ``prior_response``
    set but not the other) raise :class:`ValueError` rather than
    rendering a half-populated repair block.

    ``reference_docs`` is the extracted text of the plan's reference URLs
    (see :func:`plan_tool.fetch.render_reference_docs_block`); it grounds
    synthesis in real documentation. ``local_code_context`` carries bounded
    excerpts for explicit seed Architecture anchors; ``local_code_anchors``
    are the resolved citations the returned Architecture must preserve.
    ``dependency_cohesion_block`` lists the plan's ``depends_on`` edges whose
    two steps share no declared production file — the claims a plan's
    frontmatter least backs, surfaced ahead of the Architecture-anchor
    evidence below (BACKLOG #252; ordering/emphasis only, never a verdict).
    Empty strings render the corresponding no-evidence notes.
    """
    if (repair_error is None) != (prior_response is None):
        raise ValueError(
            "repair_error and prior_response must both be set or both be None"
        )
    template_path = prompts_dir() / "synthesize-body.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    if repair_error is not None and prior_response is not None:
        repair_block = (
            "\n\n## Repair retry\n\n"
            "Your prior response failed validation:\n\n"
            f"    {repair_error}\n\n"
            "Prior response:\n\n"
            "```\n"
            f"{prior_response.strip()}\n"
            "```\n\n"
            "Respond again with corrected JSON addressing the validation "
            "error above. This is the last retry — a second failure aborts."
        )
    else:
        repair_block = ""
    return template.safe_substitute(
        source_text=source_text,
        reference_docs_block=_render_reference_docs_section(reference_docs),
        dependency_cohesion_block=(
            dependency_cohesion_block
            if dependency_cohesion_block.strip()
            else "_No `depends_on` edge lacks a shared declared production file._"
        ),
        local_code_context_block=(
            local_code_context
            if local_code_context.strip()
            else "_No Architecture code anchors resolved in this repository._"
        ),
        local_code_anchor_requirements_block=(
            "\n".join(f"- `{anchor}`" for anchor in local_code_anchors)
            if local_code_anchors
            else "_No local source anchor needs to be retained._"
        ),
        repair_block=repair_block,
        section_shapes_block=_render_section_shapes_block(),
        project_context_block=render_project_context_block(project_context),
    )


def _parse_body_sections_json(
    raw: str,
) -> tuple[Optional[dict[str, Optional[str]]], Optional[str]]:
    """Parse one synthesis response into ``{section: body | None}``.

    Returns ``(dict, None)`` on success or ``(None, error)`` where the
    string is folded into the repair-retry prompt. Two contract pieces
    matter here: **shape symmetry** — the parsed object's required key set
    must equal :func:`_canonical_body_section_keys` exactly (no missing
    canonical keys, no extras except recognized optional sections,
    including the deliberately-excluded ``Steps`` / ``References``) — and
    **null-not-empty** — values are either a
    non-empty string or ``None``. Empty strings are explicitly rejected
    because the renderer's precedence ladder keys on ``None`` to fall
    through to H2-extracted seed content; an empty string would mask
    that fallback.
    """
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None, "response did not contain a JSON object — expected `{...}`"
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        return None, f"response body was not valid JSON: {exc}"
    if not isinstance(obj, dict):
        return None, "response top-level was not a JSON object"

    expected = set(_canonical_body_section_keys())
    optional = set(_OPTIONAL_PLAN_BODY_SECTIONS)
    actual = set(obj.keys())
    missing = expected - actual
    if missing:
        return None, f"missing canonical keys: {sorted(missing)}"
    extras = actual - expected - optional
    if extras:
        return None, f"extra keys not allowed: {sorted(extras)}"

    out: dict[str, Optional[str]] = {}
    for key in (*_canonical_body_section_keys(), *_OPTIONAL_PLAN_BODY_SECTIONS):
        if key not in obj:
            continue
        value = obj[key]
        if value is None:
            if key in expected:
                out[key] = None
            continue
        if not isinstance(value, str):
            return None, (
                f"value for key {key!r} must be a string or null; got "
                f"{type(value).__name__}"
            )
        stripped = value.strip()
        if not stripped:
            return None, (
                f"value for key {key!r} must be a string or null; got "
                "empty string (return null when no source content fits)"
            )
        out[key] = stripped
    return out, None


def _attempt_body_sections(
    raw: str,
    *,
    local_code_anchors: tuple[str, ...] = (),
) -> tuple[Optional[dict[str, Optional[str]]], Optional[str]]:
    """Run one parse + validation pass on a synthesis response.

    Thin wrapper around :func:`_parse_body_sections_json` kept as a
    separate symbol so the repair-retry control flow in
    :func:`propose_body_sections` factors cleanly, and so tests can
    monkeypatch validation in isolation if a follow-up step adds a
    graph-style check.
    """
    draft, error = _parse_body_sections_json(raw)
    if draft is None or error is not None or not local_code_anchors:
        return draft, error
    architecture = draft.get("Architecture") or ""
    missing = [
        anchor for anchor in local_code_anchors if f"`{anchor}`" not in architecture
    ]
    if missing:
        return None, (
            "Architecture must retain every resolved repository anchor: "
            f"{missing}"
        )
    return draft, None


def propose_body_sections(
    source_text: str,
    invoker: ClaudeInvoker,
    *,
    reference_docs: str = "",
    local_code_context: str = "",
    local_code_anchors: tuple[str, ...] = (),
    dependency_cohesion_block: str = "",
    project_context: str = "",
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
    iteration: int = 0,
) -> dict[str, Optional[str]]:
    """Ask claude to synthesize plan body sections from seed prose.

    Returns a ``dict`` keyed by :func:`_canonical_body_section_keys`
    where every value is either a non-empty markdown string or
    ``None``. The all-null dict (every canonical key → ``None``) is the
    explicit signal for "synthesis ran but produced no usable content";
    callers should treat it the same as a per-key ``None`` and fall
    through to H2-extraction or the ``_(TODO)_`` placeholder rather
    than aborting.

    Failure handling: one initial call, one repair retry on shape
    failure (with the prior response and error folded into the prompt),
    and an all-null dict on exhaustion. A single stderr line names the
    first-attempt error so
    repeated synthesis failures surface in run logs.

    When ``slug``, ``output_dir``, and ``repo_root`` are all provided
    the response is memoized under
    ``.plan-tool/checkpoints/<slug>/create-body-sections.json``.
    ``resume=False`` skips the load but still saves on success — so a
    ``--no-resume`` run primes the cache for the next run. An empty
    ``source_text`` is the caller's bug, not the helper's: the helper
    does not pre-validate input length (there is no seed size cap; the
    distill first-pass is the gate — see
    :func:`propose_distilled_seed_from_claude`).

    ``local_code_context`` is pre-read, repository-local evidence for explicit
    Architecture anchors. It stays an input rather than reaching into the
    filesystem here, so the helper remains easy to exercise in isolation.
    ``local_code_anchors`` contains the resolved citations that the generated
    Architecture must preserve for durable provenance. ``dependency_cohesion_block``
    is the rendered, pre-computed list of ``depends_on`` edges sharing no
    declared production file (BACKLOG #252) — also an input rather than a
    computation here, for the same isolation reason.
    """
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    if not project_context and repo_root is not None:
        project_context = _project_context_block(repo_root)
    prompt = _render_synthesis_prompt(
        source_text,
        reference_docs=reference_docs,
        local_code_context=local_code_context,
        local_code_anchors=local_code_anchors,
        dependency_cohesion_block=dependency_cohesion_block,
        project_context=project_context,
    )

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _body_sections_input_hash(
            slug,
            source_text,
            output_dir,
            repo_root,
            reference_docs=reference_docs,
            local_code_context=local_code_context,
            dependency_cohesion_block=dependency_cohesion_block,
            project_context=project_context,
            iteration=iteration,
        )
        ckpt_name = (
            _BODY_SECTIONS_CHECKPOINT_NAME
            if iteration == 0
            else f"{_BODY_SECTIONS_CHECKPOINT_NAME}-iter{iteration}"
        )
        ckpt_path = checkpoint_path(repo_root, slug, ckpt_name)

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if (
        cached is not None
        and run_logger is not None
        and input_hash is not None
    ):
        run_logger.checkpoint_hit(
            _BODY_SECTIONS_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached body-sections synthesis (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _BODY_SECTIONS_CHECKPOINT_NAME, "force"
                )
            cached = None

    # False unless the else-branch advisory ran — gates the backstop on the
    # primary send only (the repair retry below measures its own prompt; see
    # propose_steps_from_claude).
    budget_covered = False
    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Synthesizing plan body sections (resumed from checkpoint)"
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        prompt_bytes = len(prompt.encode("utf-8"))
        synthesis_blocks = [("seed", len(source_text.encode("utf-8")))]
        if reference_docs:
            synthesis_blocks.append(
                ("reference-docs", len(reference_docs.encode("utf-8")))
            )
        if local_code_context:
            synthesis_blocks.append(
                ("repository-code", len(local_code_context.encode("utf-8")))
            )
        if dependency_cohesion_block:
            synthesis_blocks.append(
                (
                    "dependency-cohesion",
                    len(dependency_cohesion_block.encode("utf-8")),
                )
            )
        if project_context:
            synthesis_blocks.append(
                ("project-context", len(project_context.encode("utf-8")))
            )
        budget_covered = _maybe_warn_create_budget(
            total_bytes=prompt_bytes,
            blocks=synthesis_blocks,
            phase="create-synthesis",
            surface="create body synthesis",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        if run_logger is not None:
            run_logger.install_call_end_sink(
                phase="propose_body_sections", attempt=1
            )
        try:
            handle = reporter.start_step(
                1, 1, "Synthesizing plan body sections",
                phase="propose_body_sections",
                attempt=1,
                prompt_bytes=prompt_bytes,
                prompt_sha256=hash_prompt(prompt),
            )
            start = time.monotonic()
            with suppress_prompt_budget_backstop(active=budget_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_body_sections",
                    attempt=1,
                    start=start,
                )
            elapsed = time.monotonic() - start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()

    draft, error = _attempt_body_sections(
        raw, local_code_anchors=local_code_anchors
    )
    if draft is None:
        tool(f"body-sections synthesis: first attempt failed ({error}); retrying once")
        repair_prompt = _render_synthesis_prompt(
            source_text,
            reference_docs=reference_docs,
            local_code_context=local_code_context,
            local_code_anchors=local_code_anchors,
            dependency_cohesion_block=dependency_cohesion_block,
            project_context=project_context,
            repair_error=error,
            prior_response=raw,
        )
        if run_logger is not None:
            run_logger.claude_call_start(
                phase="propose_body_sections", attempt=2,
                prompt_bytes=len(repair_prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(repair_prompt),
            )
            run_logger.install_call_end_sink(
                phase="propose_body_sections", attempt=2
            )
        # Measure the actual (larger) repair prompt — it embeds the full
        # rejected response via prior_response — so an oversized repair still
        # gets a scoped advisory (see propose_steps_from_claude).
        repair_covered = _maybe_warn_create_budget(
            total_bytes=len(repair_prompt.encode("utf-8")),
            blocks=[("rejected-response", len(raw.encode("utf-8")))],
            phase="create-synthesis",
            surface="create body synthesis",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        try:
            retry_start = time.monotonic()
            with suppress_prompt_budget_backstop(active=repair_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(repair_prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_body_sections",
                    attempt=2,
                    start=retry_start,
                    base_elapsed=elapsed,
                )
            elapsed += time.monotonic() - retry_start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()
        draft, error = _attempt_body_sections(
            raw, local_code_anchors=local_code_anchors
        )

    if draft is None:
        handle.fail(
            elapsed,
            f"body-sections synthesis failed after one repair retry: {error}",
        )
        return {key: None for key in _canonical_body_section_keys()}

    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save body-sections checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _BODY_SECTIONS_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )

    handle.complete(elapsed, len(raw.encode("utf-8")))
    return draft


def _render_numbered_source(source_text: str) -> str:
    """Prefix each seed line with its 1-based number + tab for the distill prompt.

    Line numbers let the model cite accurate ``start_line``/``end_line`` ranges
    in split proposals and evidence spans; they are ignored for derived prose.
    """
    lines = source_text.splitlines()
    return "\n".join(f"{i}\t{line}" for i, line in enumerate(lines, start=1))


def _render_distill_prompt(
    source_text: str,
    *,
    repair_error: Optional[str] = None,
    prior_response: Optional[str] = None,
) -> str:
    """Load ``prompts/distill-seed.md`` and substitute the placeholders.

    Mirrors :func:`_render_synthesis_prompt`'s repair-block contract: both
    ``repair_error`` and ``prior_response`` set appends a repair block; both
    ``None`` is the initial call; a mixed pair raises :class:`ValueError`.
    """
    if (repair_error is None) != (prior_response is None):
        raise ValueError(
            "repair_error and prior_response must both be set or both be None"
        )
    template_path = prompts_dir() / "distill-seed.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    if repair_error is not None and prior_response is not None:
        repair_block = (
            "\n\n## Repair retry\n\n"
            "Your prior response failed validation:\n\n"
            f"    {repair_error}\n\n"
            "Prior response:\n\n"
            "```\n"
            f"{prior_response.strip()}\n"
            "```\n\n"
            "Respond again with corrected JSON addressing the error above. "
            "This is the last retry — a second failure aborts distillation."
        )
    else:
        repair_block = ""
    return template.safe_substitute(
        numbered_source=_render_numbered_source(source_text),
        repair_block=repair_block,
        section_shapes_block=_render_section_shapes_block(),
    )


def _render_direct_split_assessment_prompt(source_text: str) -> str:
    """Render the direct route's decision-only raw-source prompt."""
    return (
        "Assess whether this file-backed plan source is one cohesive plan or "
        "must be split into multiple independent plans. Preserve the source; "
        "do not rewrite, summarize, or provide replacement sections.\n\n"
        "Return exactly one JSON object and nothing else:\n"
        '- one plan: {"outcome":"single"}\n'
        '- multiple plans: {"outcome":"split","plans":[{"title":"...",'
        '"suggested_slug":"...","rationale":"...","start_line":1,'
        '"end_line":1}, ...]}\n\n'
        "A split requires at least two plans. Line ranges are 1-based and "
        "refer to the raw source below.\n\n"
        "## Raw source\n\n"
        "```markdown\n"
        f"{source_text.rstrip()}\n"
        "```\n"
    )


def _parse_direct_split_assessment_json(
    raw: str, *, total_lines: int
) -> tuple[Optional[DirectSplitAssessment], Optional[str]]:
    """Accept only the direct route's single-or-shared-split decision."""
    try:
        obj = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        return None, f"response body was not valid JSON: {exc}"
    if not isinstance(obj, dict):
        return None, "response top-level was not a JSON object"

    outcome = obj.get("outcome")
    if outcome == "single":
        if set(obj) != {"outcome"}:
            return None, "single-plan decision must not include replacement content"
        return DirectSplitAssessment(), None
    if outcome == "split":
        if set(obj) != {"outcome", "plans"}:
            return None, "split decision must contain only `outcome` and `plans`"
        plans = obj.get("plans")
        if not isinstance(plans, list):
            return None, "split outcome requires a `plans` array"
        entries, error = _validate_split_plans(plans, total_lines=total_lines)
        if entries is None:
            return None, error
        return DirectSplitAssessment(split=entries), None
    return None, f'`outcome` must be "single" or "split"; got {outcome!r}'


def assess_direct_source_split_from_claude(
    source_text: str,
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> DirectSplitAssessment:
    """Make one fail-closed single-versus-split decision for raw source text."""
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    prompt = _render_direct_split_assessment_prompt(source_text)
    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _direct_assessment_input_hash(
            slug, source_text, prompt, output_dir, repo_root
        )
        ckpt_path = checkpoint_path(
            repo_root, slug, _DIRECT_ASSESSMENT_CHECKPOINT_NAME
        )
    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if cached is not None and run_logger is not None and input_hash is not None:
        run_logger.checkpoint_hit(
            _DIRECT_ASSESSMENT_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )
    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached direct-source assessment (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _DIRECT_ASSESSMENT_CHECKPOINT_NAME, "force"
                )
            cached = None

    prompt_bytes = len(prompt.encode("utf-8"))
    if cached is not None:
        handle = reporter.start_step(
            1,
            1,
            "Assessing file-backed source split (resumed from checkpoint)",
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        handle = reporter.start_step(
            1,
            1,
            "Assessing file-backed source split",
            phase="assess_direct_source_split",
            attempt=1,
            prompt_bytes=prompt_bytes,
            prompt_sha256=hash_prompt(prompt),
        )
        started = time.monotonic()
        if run_logger is not None:
            run_logger.install_call_end_sink(
                phase="assess_direct_source_split", attempt=1
            )
        try:
            raw = _invoke_or_fail(
                lambda: invoker(prompt),
                handle=handle,
                run_logger=run_logger,
                phase="assess_direct_source_split",
                attempt=1,
                start=started,
            )
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()
        elapsed = time.monotonic() - started
    assessment, error = _parse_direct_split_assessment_json(
        raw, total_lines=len(source_text.splitlines())
    )
    if assessment is None:
        if cached is not None and ckpt_path is not None:
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _DIRECT_ASSESSMENT_CHECKPOINT_NAME, "invalid"
                )
        handle.fail(elapsed, f"direct source split assessment failed: {error}")
        if run_logger is not None:
            run_logger.attempt_failed(
                phase="assess_direct_source_split", attempt=1, failure_kind="parse"
            )
        raise CreateError(
            "direct source split assessment is invalid; no plan was written: "
            f"{error}"
        )
    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save direct-assessment checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _DIRECT_ASSESSMENT_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )
    handle.complete(elapsed, len(raw.encode("utf-8")))
    return assessment


def _render_risk_profile_prompt(source_text: str) -> str:
    """Render the hermetic seed-only risk-classification prompt."""
    template_path = prompts_dir() / "classify-risk-profile.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.safe_substitute(seed_text=source_text)


def _render_distilled_markdown(sections: dict[str, Optional[str]]) -> str:
    """Assemble canonical-shaped markdown from a distilled ``sections`` dict.

    Emits ``## <Section>`` + body for each non-null canonical or recognized
    optional section (``Steps`` / ``References`` excluded — they're owned by
    other round-trips). The result feeds the steps /
    references / body round-trips as the cleaned seed: ``extract_h2_sections``
    re-parses these headings, and when every canonical key is present
    :func:`_canonical_seed_covers_all` skips the body-synthesis round-trip.
    """
    parts: list[str] = []
    for section in _canonical_body_section_keys():
        body = sections.get(section)
        if body is None:
            continue
        body = body.strip()
        if not body:
            continue
        parts.append(f"## {section}\n\n{body}")
    for section in _OPTIONAL_PLAN_BODY_SECTIONS:
        body = sections.get(section)
        if body is None:
            continue
        body = body.strip()
        if not body:
            continue
        parts.append(f"## {section}\n\n{body}")
    return "\n\n".join(parts) + ("\n" if parts else "")


def _clamp_line_range(
    start: object, end: object, total_lines: int
) -> tuple[Optional[int], Optional[int]]:
    """Clamp a model-proposed ``[start, end]`` to ``[1, total_lines]``.

    Returns ``(None, None)`` when the range is unusable (non-int, or inverted
    after clamping) so the renderer can fall back to printing the title +
    rationale without a carve command. LLM line-counting drifts, so the range
    is advisory, not load-bearing.
    """
    if total_lines < 1:
        return None, None
    if not isinstance(start, int) or isinstance(start, bool):
        return None, None
    if not isinstance(end, int) or isinstance(end, bool):
        return None, None
    clamped_start = max(1, min(start, total_lines))
    clamped_end = max(1, min(end, total_lines))
    if clamped_start > clamped_end:
        return None, None
    return clamped_start, clamped_end


def _validate_distilled_sections(
    sections: dict,
) -> tuple[Optional[dict[str, Optional[str]]], Optional[str]]:
    """Validate the single-plan ``sections`` object from a distill response.

    The three intent-derived canonical sections must be useful prose. The
    evidence-only sections may be ``null`` here; their separate source spans
    decide whether non-null text is publishable.
    """
    expected = set(_canonical_body_section_keys())
    optional = set(_OPTIONAL_PLAN_BODY_SECTIONS)
    actual = set(sections.keys())
    missing = expected - actual
    if missing:
        return None, f"missing canonical section keys: {sorted(missing)}"
    extras = actual - expected - optional
    if extras:
        return None, f"section keys not allowed: {sorted(extras)}"
    out: dict[str, Optional[str]] = {}
    for key in (*_canonical_body_section_keys(), *_OPTIONAL_PLAN_BODY_SECTIONS):
        if key not in sections:
            continue
        value = sections[key]
        if value is None:
            if key in _DERIVE_FROM_INTENT_SECTIONS:
                return None, f"derived section {key!r} must be a non-empty string"
            if key in expected:
                out[key] = None
            continue
        if not isinstance(value, str):
            return None, (
                f"value for section {key!r} must be a string or null; got "
                f"{type(value).__name__}"
            )
        cleaned = value.strip()
        if key in _DERIVE_FROM_INTENT_SECTIONS and (
            not cleaned or _is_placeholder_section(cleaned)
        ):
            return None, f"derived section {key!r} must be non-empty prose"
        out[key] = cleaned or None
    return out, None


def _preserve_source_optional_sections(
    sections: dict[str, Optional[str]], *, source_text: str
) -> tuple[Optional[dict[str, Optional[str]]], Optional[str], bool]:
    """Retain source optional context and mark prose-backed Input for citation."""
    source_sections = extract_h2_sections(source_text, ignore_fenced_code=True)
    preserved = sections.copy()
    input_needs_evidence = False
    for section in _OPTIONAL_PLAN_BODY_SECTIONS:
        source_body = source_sections.get(section.lower(), "").strip()
        supplied = bool(source_body) and not _is_placeholder_section(source_body)
        if section == "Input":
            if supplied:
                preserved[section] = source_body
            elif section in preserved:
                input_needs_evidence = True
            continue
        if section in preserved and not supplied:
            return (
                None,
                f"optional section {section!r} was not supplied by the raw source",
                False,
            )
        if supplied:
            preserved[section] = source_body
    return preserved, None, input_needs_evidence


def _evidence_only_body_section_keys() -> tuple[str, ...]:
    """Return canonical sections whose published text needs source spans."""
    return tuple(
        key
        for key in _canonical_body_section_keys()
        if key not in _DERIVE_FROM_INTENT_SECTIONS
    )


def _unsupported_normalized_evidence_section(
    sections: dict[str, Optional[str]],
    evidence_spans: dict[str, Optional[tuple[tuple[int, int], ...]]],
) -> Optional[str]:
    """Return the first evidence-only section without retained support."""
    for section_name in _evidence_only_body_section_keys():
        materialized = sections.get(section_name)
        spans = evidence_spans.get(section_name)
        if section_name == "Deferred" and spans is None and (
            not isinstance(materialized, str) or not materialized.strip()
        ):
            continue
        if not isinstance(materialized, str) or not materialized.strip():
            return section_name
        if not isinstance(spans, tuple) or not spans:
            return section_name
        previous_end = 0
        for span in spans:
            if (
                not isinstance(span, tuple)
                or len(span) != 2
                or not isinstance(span[0], int)
                or isinstance(span[0], bool)
                or not isinstance(span[1], int)
                or isinstance(span[1], bool)
                or span[0] < 1
                or span[1] < span[0]
                or span[0] <= previous_end
            ):
                return section_name
            previous_end = span[1]
    return None


def _unsupported_evidence_refusal(section_name: str) -> str:
    """Name both causes: the seed lacks the section's text, or the model cited none of it.

    The refusal discards the distill checkpoint, so a re-run prepares the seed afresh.
    """
    return (
        f"normalized evidence for {section_name!r} is unsupported: preparation "
        "cited no source text in the seed for it. If the seed states nothing for "
        f"it, add a '## {section_name}' section with that text and re-run; if it "
        "already does, re-run unchanged"
    )


def _materialize_evidence_spans(
    raw_spans: object,
    *,
    source_lines: list[str],
    section_name: str,
) -> tuple[Optional[tuple[tuple[int, int], ...]], Optional[str], Optional[str]]:
    """Validate source-order spans and return their exact source text."""
    if raw_spans is None:
        return None, None, None
    if not isinstance(raw_spans, list) or not raw_spans:
        return None, None, (
            f"evidence spans for {section_name!r} must be null or a non-empty list"
        )

    validated: list[tuple[int, int]] = []
    materialized: list[str] = []
    previous_end = 0
    for index, raw_span in enumerate(raw_spans):
        if not isinstance(raw_span, dict) or set(raw_span) != {
            "start_line",
            "end_line",
        }:
            return None, None, (
                f"evidence span {section_name}[{index}] must contain only "
                "`start_line` and `end_line`"
            )
        start_line = raw_span["start_line"]
        end_line = raw_span["end_line"]
        if (
            not isinstance(start_line, int)
            or isinstance(start_line, bool)
            or not isinstance(end_line, int)
            or isinstance(end_line, bool)
        ):
            return None, None, (
                f"evidence span {section_name}[{index}] line bounds must be integers"
            )
        if start_line < 1 or end_line < start_line or end_line > len(source_lines):
            return None, None, (
                f"evidence span {section_name}[{index}] is outside raw source lines"
            )
        if start_line <= previous_end:
            return None, None, (
                f"evidence spans for {section_name!r} must be source-ordered "
                "and non-overlapping"
            )
        lines = source_lines[start_line - 1 : end_line]
        body_lines = [
            line
            for line in lines
            if line.strip() and not re.match(r"^ {0,3}#{1,6}(?:[ \t]|$)", line)
        ]
        if not body_lines:
            return None, None, (
                f"evidence span {section_name}[{index}] selects a heading without body text"
            )
        validated.append((start_line, end_line))
        materialized.append("\n".join(lines).strip())
        previous_end = end_line
    return tuple(validated), "\n\n".join(materialized), None


def _validate_and_materialize_evidence_sections(
    sections: dict[str, Optional[str]],
    evidence_spans: object,
    *,
    source_text: str,
    input_needs_evidence: bool = False,
) -> tuple[
    Optional[dict[str, Optional[str]]],
    Optional[dict[str, Optional[tuple[tuple[int, int], ...]]]],
    Optional[str],
]:
    """Replace evidence-backed model prose with validated raw-source text."""
    if not isinstance(evidence_spans, dict):
        return None, None, "normalized outcome requires an `evidence_spans` object"
    evidence_keys = _evidence_only_body_section_keys() + (
        ("Input",) if input_needs_evidence else ()
    )
    if set(evidence_spans) != set(evidence_keys):
        return None, None, (
            "evidence spans must contain exactly the required keys: "
            f"{list(evidence_keys)}"
        )

    materialized_sections = sections.copy()
    validated_map: dict[str, Optional[tuple[tuple[int, int], ...]]] = {}
    source_lines = source_text.splitlines()
    for section_name in evidence_keys:
        if section_name == "Input" and evidence_spans[section_name] is None:
            return None, None, (
                "evidence spans for 'Input' must be a non-empty list"
            )
        validated, materialized, error = _materialize_evidence_spans(
            evidence_spans[section_name],
            source_lines=source_lines,
            section_name=section_name,
        )
        if error is not None:
            return None, None, error
        validated_map[section_name] = validated
        # A model string is never source support. A null span stays visible as
        # an evidence gap; prose-backed Input rejects null before this call.
        materialized_sections[section_name] = materialized
    return materialized_sections, validated_map, None


def _normalized_sections_cover_all(
    sections: dict[str, Optional[str]],
) -> bool:
    """Whether a normalized map can replace body synthesis completely."""
    return all(
        isinstance(sections.get(key), str) and bool(sections[key].strip())
        for key in _canonical_body_section_keys()
    )


def _validate_split_plans(
    plans: list, *, total_lines: int
) -> tuple[Optional[list[SplitProposalEntry]], Optional[str]]:
    """Validate the ``plans`` array from a split-outcome distill response.

    Requires >= 2 entries (a single-entry "split" is just one plan and is a
    shape error). Line ranges are clamped via :func:`_clamp_line_range`; an
    unusable range degrades to ``None``/``None`` on the entry rather than
    failing the whole parse.
    """
    if len(plans) < 2:
        return None, (
            'split outcome requires >= 2 plans; use outcome "single" for one '
            "cohesive plan"
        )
    entries: list[SplitProposalEntry] = []
    for i, item in enumerate(plans):
        if not isinstance(item, dict):
            return None, f"plan[{i}] must be a JSON object"
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            return None, f"plan[{i}] is missing a non-empty `title`"
        slug = item.get("suggested_slug")
        if not isinstance(slug, str) or not slug.strip():
            return None, f"plan[{i}] is missing a non-empty `suggested_slug`"
        rationale = item.get("rationale")
        rationale = rationale.strip() if isinstance(rationale, str) else ""
        start_line, end_line = _clamp_line_range(
            item.get("start_line"), item.get("end_line"), total_lines
        )
        entries.append(
            SplitProposalEntry(
                title=title.strip(),
                suggested_slug=slug.strip(),
                rationale=rationale,
                start_line=start_line,
                end_line=end_line,
            )
        )
    return entries, None


def _parse_distill_json(
    raw: str, *, source_text: str, total_lines: Optional[int] = None
) -> tuple[Optional[DistillOutcome], Optional[str]]:
    """Parse one distill response into a :class:`DistillOutcome`.

    Returns ``(outcome, None)`` on success or ``(None, error)`` for the repair
    retry. Enforces the model-owned discriminator from
    ``prompts/distill-seed.md``: ``outcome`` is ``"single"`` (a normalized
    section map plus source spans) or ``"split"`` (a plans array of >= 2
    entries). Refusal is owned by :func:`propose_distilled_seed_from_claude`.
    """
    text = raw.strip()
    if not text.startswith("{") or not text.endswith("}"):
        return None, "response must be one JSON object with no surrounding prose"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"response body was not valid JSON: {exc}"
    if not isinstance(obj, dict):
        return None, "response top-level was not a JSON object"

    line_count = len(source_text.splitlines())
    if total_lines is not None and total_lines != line_count:
        return None, "raw source line count did not match parser input"

    outcome = obj.get("outcome")
    if outcome == "single":
        if set(obj) != {"outcome", "sections", "evidence_spans"}:
            return None, (
                "single-plan outcome must contain only `outcome`, `sections`, "
                "and `evidence_spans`"
            )
        sections = obj.get("sections")
        if not isinstance(sections, dict):
            return None, 'single-plan outcome requires a `sections` object'
        parsed, err = _validate_distilled_sections(sections)
        if parsed is None:
            return None, err
        parsed, err, input_needs_evidence = _preserve_source_optional_sections(
            parsed, source_text=source_text
        )
        if parsed is None:
            return None, err
        materialized, spans, err = _validate_and_materialize_evidence_sections(
            parsed,
            obj.get("evidence_spans"),
            source_text=source_text,
            input_needs_evidence=input_needs_evidence,
        )
        if materialized is None or spans is None:
            return None, err
        return DistillOutcome.normalized(materialized, spans), None
    if outcome == "split":
        if set(obj) != {"outcome", "plans"}:
            return None, "split outcome must contain only `outcome` and `plans`"
        plans = obj.get("plans")
        if not isinstance(plans, list):
            return None, "split outcome requires a `plans` array"
        entries, err = _validate_split_plans(plans, total_lines=line_count)
        if entries is None:
            return None, err
        return DistillOutcome.split_proposal(entries), None
    return None, f'`outcome` must be "single" or "split"; got {outcome!r}'


def propose_distilled_seed_from_claude(
    source_text: str,
    invoker: ClaudeInvoker,
    *,
    reporter: Optional[ProgressReporter] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    input_fn: Optional[InputFn] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> DistillOutcome:
    """Prepare raw source as normalized prose, a split, or a refusal.

    Models :func:`propose_body_sections` — checkpoint/resume, one repair retry,
    a ``propose_distilled_seed`` run-logger phase. Returns a
    :class:`DistillOutcome`; parse failure after the repair retry returns an
    explicit refusal. The file-backed caller then stops before authoring.

    Memoized under ``.plan-tool/checkpoints/<slug>/create-distill-seed.json``
    when ``slug`` / ``output_dir`` / ``repo_root`` are all provided. Distill
    runs once per create (never inside the convergence loop), so there is no
    ``iteration`` keyspace.
    """
    if reporter is None:
        reporter = StderrReporter(run_log=run_logger)
    total_lines = len(source_text.splitlines())
    prompt = _render_distill_prompt(source_text)

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _distill_seed_input_hash(
            slug, source_text, output_dir, repo_root, rendered_prompt=prompt
        )
        ckpt_path = checkpoint_path(
            repo_root, slug, _DISTILL_SEED_CHECKPOINT_NAME
        )

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None and input_hash is not None)
        else None
    )
    if cached is not None and run_logger is not None and input_hash is not None:
        run_logger.checkpoint_hit(
            _DISTILL_SEED_CHECKPOINT_NAME,
            input_hash,
            len(cached.payload.encode("utf-8")),
        )

    if cached is not None and input_fn is not None and sys.stdin.isatty():
        age = _checkpoint_age_minutes(cached)
        if not _ask_yn(
            input_fn,
            f"Resume cached seed distillation (~{age}m old)?",
            default=True,
        ):
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(
                    _DISTILL_SEED_CHECKPOINT_NAME, "force"
                )
            cached = None

    # False unless the else-branch advisory ran — gates the backstop on the
    # primary send only (the repair retry below measures its own prompt; see
    # propose_steps_from_claude).
    budget_covered = False
    if cached is not None:
        handle = reporter.start_step(
            1, 1, "Distilling seed (resumed from checkpoint)"
        )
        raw = cached.payload
        elapsed = 0.0
    else:
        prompt_bytes = len(prompt.encode("utf-8"))
        budget_covered = _maybe_warn_create_budget(
            total_bytes=prompt_bytes,
            blocks=[("seed", len(source_text.encode("utf-8")))],
            phase="create-distill",
            surface="create seed distillation",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        if run_logger is not None:
            run_logger.install_call_end_sink(
                phase="propose_distilled_seed", attempt=1
            )
        try:
            handle = reporter.start_step(
                1, 1, "Distilling seed",
                phase="propose_distilled_seed",
                attempt=1,
                prompt_bytes=prompt_bytes,
                prompt_sha256=hash_prompt(prompt),
            )
            start = time.monotonic()
            with suppress_prompt_budget_backstop(active=budget_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_distilled_seed",
                    attempt=1,
                    start=start,
                )
            elapsed = time.monotonic() - start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()

    outcome, error = _parse_distill_json(
        raw, source_text=source_text, total_lines=total_lines
    )
    if outcome is None:
        if cached is not None and ckpt_path is not None:
            discard_checkpoint(ckpt_path)
            if run_logger is not None:
                run_logger.checkpoint_discard(_DISTILL_SEED_CHECKPOINT_NAME, "invalid")
            cached = None
        tool(f"seed distillation: first attempt failed ({error}); retrying once")
        repair_prompt = _render_distill_prompt(
            source_text, repair_error=error, prior_response=raw
        )
        if run_logger is not None:
            run_logger.claude_call_start(
                phase="propose_distilled_seed", attempt=2,
                prompt_bytes=len(repair_prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(repair_prompt),
            )
            run_logger.install_call_end_sink(
                phase="propose_distilled_seed", attempt=2
            )
        # Measure the actual (larger) repair prompt — it embeds the full
        # rejected response via prior_response — so an oversized repair still
        # gets a scoped advisory (see propose_steps_from_claude).
        repair_covered = _maybe_warn_create_budget(
            total_bytes=len(repair_prompt.encode("utf-8")),
            blocks=[("rejected-response", len(raw.encode("utf-8")))],
            phase="create-distill",
            surface="create seed distillation",
            repo_root=repo_root,
            plan_slug=slug or "",
        )
        try:
            retry_start = time.monotonic()
            with suppress_prompt_budget_backstop(active=repair_covered):
                raw = _invoke_or_fail(
                    lambda: invoker(repair_prompt),
                    handle=handle,
                    run_logger=run_logger,
                    phase="propose_distilled_seed",
                    attempt=2,
                    start=retry_start,
                    base_elapsed=elapsed,
                )
            elapsed += time.monotonic() - retry_start
        finally:
            if run_logger is not None:
                run_logger.uninstall_call_end_sink()
        outcome, error = _parse_distill_json(
            raw, source_text=source_text, total_lines=total_lines
        )

    if outcome is None:
        handle.fail(
            elapsed,
            f"seed distillation failed after one repair retry: {error}",
        )
        return DistillOutcome.refused(
            f"seed preparation remained invalid after one repair: {error}"
        )

    if ckpt_path is not None and input_hash is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save distill checkpoint {ckpt_path} ({exc}); "
                "resume on next run will not be available for this phase"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _DISTILL_SEED_CHECKPOINT_NAME,
                    input_hash,
                    len(raw.encode("utf-8")),
                )

    handle.complete(elapsed, len(raw.encode("utf-8")))
    return outcome


_RISK_PROFILE_EVIDENCE_KEYS = frozenset(
    {"deletion_dominance", "no_consumer", "no_new_surface"}
)
_RISK_PROFILE_FALLBACK_RATIONALE = (
    "Risk classification defaults to standard because the seed did not establish "
    "all low-risk conditions."
)
_RISK_PROFILE_CONSUMER_TERMS = r"(?:consumers?|callers?|clients?|dependents?)"
_RISK_PROFILE_AUTH_TERMS = r"(?:auth|authn|authz|authentication|authorization)"
_RISK_PROFILE_SURFACE_TERMS = r"(?:external|schema|api|contract|runtime)"
_RISK_PROFILE_NEGATED_LIST_SEPARATOR = (
    r"\s*(?:,\s*(?:(?:and|or)\s+)?|(?:and|or)\s+)"
)
_RISK_PROFILE_NEGATED_CONSUMER_LIST = (
    rf"{_RISK_PROFILE_CONSUMER_TERMS}(?:{_RISK_PROFILE_NEGATED_LIST_SEPARATOR}"
    rf"{_RISK_PROFILE_CONSUMER_TERMS})*"
)
_RISK_PROFILE_NEGATED_AUTH_LIST = (
    rf"{_RISK_PROFILE_AUTH_TERMS}(?:{_RISK_PROFILE_NEGATED_LIST_SEPARATOR}"
    rf"{_RISK_PROFILE_AUTH_TERMS})*"
)
_RISK_PROFILE_NEGATED_SURFACE_LIST = (
    rf"{_RISK_PROFILE_SURFACE_TERMS}(?:{_RISK_PROFILE_NEGATED_LIST_SEPARATOR}"
    rf"{_RISK_PROFILE_SURFACE_TERMS})*"
)
_RISK_PROFILE_NEGATIVE_CONSUMER_RE = re.compile(
    rf"\b(?:no|zero)\s+(?:named\s+)?{_RISK_PROFILE_NEGATED_CONSUMER_LIST}\b"
    rf"|\bwithout\s+(?:any\s+)?{_RISK_PROFILE_NEGATED_CONSUMER_LIST}\b",
    re.IGNORECASE,
)
_RISK_PROFILE_NEGATIVE_TERM_RE = {
    "contract": re.compile(
        r"\b(?:no|zero)\s+(?:new\s+)?contracts?\b"
        r"|\bwithout\s+(?:a\s+)?contracts?\b"
        r"|\bdoes not\s+(?:add|change|alter|extend)\s+(?:a\s+)?contracts?\b",
        re.IGNORECASE,
    ),
    "migration": re.compile(
        r"\b(?:no|zero)\s+migrations?\b|\bwithout\s+(?:a\s+)?migration\b",
        re.IGNORECASE,
    ),
    "auth": re.compile(
        rf"\b(?:no|zero)\s+{_RISK_PROFILE_NEGATED_AUTH_LIST}\b"
        rf"|\bwithout\s+(?:any\s+)?{_RISK_PROFILE_NEGATED_AUTH_LIST}\b",
        re.IGNORECASE,
    ),
}
_RISK_PROFILE_NEGATIVE_SURFACE_RE = re.compile(
    rf"\b(?:no|zero)\s+(?:new\s+)?{_RISK_PROFILE_NEGATED_SURFACE_LIST}"
    r"(?:\s+surface)?\b"
    rf"|\bwithout\s+(?:any\s+)?(?:new\s+)?{_RISK_PROFILE_NEGATED_SURFACE_LIST}"
    r"(?:\s+surface)?\b"
    r"|\b(?:does not|doesn't|do not|will not)\s+"
    r"(?:add|introduce|create|extend)\s+(?:a\s+|any\s+)?(?:new\s+)?"
    rf"{_RISK_PROFILE_NEGATED_SURFACE_LIST}(?:\s+surface)?\b",
    re.IGNORECASE,
)
_RISK_PROFILE_DELETION_RE = re.compile(
    r"\b(?:delete|deletes|deleting|deletion|remove|removes|removing|removal|"
    r"retire|retires|retiring|retirement|drop|drops|dropping)\b",
    re.IGNORECASE,
)
_RISK_PROFILE_NEGATIVE_DELETION_RE = re.compile(
    r"\b(?:no|zero)\s+(?:deletions?|removals?|retirements?|drops?)\b"
    r"|\bwithout\s+(?:any\s+)?(?:deletions?|removals?|retirements?|drops?)\b"
    r"|\b(?:does not|doesn't|do not|will not|cannot|can't|not)\s+"
    r"(?:delete|deletes|deleting|remove|removes|removing|retire|retires|retiring|"
    r"drop|drops|dropping)\b",
    re.IGNORECASE,
)
_RISK_PROFILE_NO_CONSUMER_RE = re.compile(
    rf"\b(?:no|zero)\s+(?:named\s+)?{_RISK_PROFILE_NEGATED_CONSUMER_LIST}\b"
    rf"|\bwithout\s+(?:any\s+)?{_RISK_PROFILE_NEGATED_CONSUMER_LIST}\b"
    r"|\b(?:unused|unreferenced|not called)\b",
    re.IGNORECASE,
)
_RISK_PROFILE_SURFACE_WORDS = (
    "external",
    "schema",
    "api",
    "contract",
    "runtime",
)
_RISK_PROFILE_CONSUMER_MENTION_RE = re.compile(
    rf"\b{_RISK_PROFILE_CONSUMER_TERMS}\b", re.IGNORECASE
)
_RISK_PROFILE_CONTRACT_MENTION_RE = re.compile(r"\bcontracts?\b", re.IGNORECASE)
_RISK_PROFILE_MIGRATION_MENTION_RE = re.compile(
    r"\bmigrat(?:e|es|ed|ing|ion|ions)\b", re.IGNORECASE
)
_RISK_PROFILE_AUTH_MENTION_RE = re.compile(
    rf"\b{_RISK_PROFILE_AUTH_TERMS}\b", re.IGNORECASE
)
_RISK_PROFILE_SURFACE_MENTION_RE = re.compile(
    rf"\b(?P<surface>{_RISK_PROFILE_SURFACE_TERMS})\b", re.IGNORECASE
)


def _one_line_text(value: object) -> Optional[str]:
    """Return a non-empty single line, or ``None`` for an invalid value."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        return None
    return stripped


def _risk_profile_has_unnegated_mention(
    text: str, mention_re: re.Pattern[str], *negative_res: re.Pattern[str]
) -> bool:
    """Return whether a semantic mention is outside every explicit negation."""
    negated_spans = [
        match.span()
        for negative_re in negative_res
        for match in negative_re.finditer(text)
    ]
    return any(
        not any(start <= mention.start() < end for start, end in negated_spans)
        for mention in mention_re.finditer(text)
    )


def _risk_profile_has_affirmative_deletion(text: str) -> bool:
    """Return whether text asserts a deletion outside an explicit negation."""
    return _risk_profile_has_unnegated_mention(
        text, _RISK_PROFILE_DELETION_RE, _RISK_PROFILE_NEGATIVE_DELETION_RE
    )


def _risk_profile_source_counter_signals(source_text: str) -> list[str]:
    """Return positive source signals that keep a proposal at standard."""
    signals: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", source_text)
    for sentence in sentences:
        for fragment in re.split(r"\b(?:but|however)\b", sentence, flags=re.IGNORECASE):
            if not fragment.strip():
                continue
            if (
                _risk_profile_has_unnegated_mention(
                    fragment,
                    _RISK_PROFILE_CONSUMER_MENTION_RE,
                    _RISK_PROFILE_NEGATIVE_CONSUMER_RE,
                )
                and "named consumer" not in signals
            ):
                signals.append("named consumer")
            if (
                _risk_profile_has_unnegated_mention(
                    fragment,
                    _RISK_PROFILE_CONTRACT_MENTION_RE,
                    _RISK_PROFILE_NEGATIVE_TERM_RE["contract"],
                    _RISK_PROFILE_NEGATIVE_SURFACE_RE,
                )
                and "contract" not in signals
            ):
                signals.append("contract")
            if (
                _risk_profile_has_unnegated_mention(
                    fragment,
                    _RISK_PROFILE_MIGRATION_MENTION_RE,
                    _RISK_PROFILE_NEGATIVE_TERM_RE["migration"],
                )
                and "migration" not in signals
            ):
                signals.append("migration")
            if (
                _risk_profile_has_unnegated_mention(
                    fragment,
                    _RISK_PROFILE_AUTH_MENTION_RE,
                    _RISK_PROFILE_NEGATIVE_TERM_RE["auth"],
                )
                and "authentication or authorization" not in signals
            ):
                signals.append("authentication or authorization")
            negative_surface_spans = [
                match.span() for match in _RISK_PROFILE_NEGATIVE_SURFACE_RE.finditer(fragment)
            ]
            for surface_match in _RISK_PROFILE_SURFACE_MENTION_RE.finditer(fragment):
                surface_start = surface_match.start()
                if any(start <= surface_start < end for start, end in negative_surface_spans):
                    continue
                surface = surface_match.group("surface").lower()
                if surface == "contract":
                    continue
                label = f"{surface} surface"
                if label not in signals:
                    signals.append(label)
    return signals


def _low_evidence_matches_admission(evidence: dict[str, str]) -> bool:
    """Check that grounded excerpts assert each low-risk admission condition."""
    deletion = evidence["deletion_dominance"]
    no_consumer = evidence["no_consumer"]
    no_new_surface = evidence["no_new_surface"].lower()
    return (
        _risk_profile_has_affirmative_deletion(deletion)
        and _RISK_PROFILE_NO_CONSUMER_RE.search(no_consumer) is not None
        and re.search(r"\b(?:no|zero)\s+new\b", no_new_surface) is not None
        and all(re.search(rf"\b{surface}\b", no_new_surface) for surface in _RISK_PROFILE_SURFACE_WORDS)
    )


def _standard_risk_profile_proposal(
    reason: str, *, source_counter_signals: tuple[str, ...] = ()
) -> _RiskProfileProposal:
    """Build the only fail-closed classifier result."""
    assert _one_line_text(reason) is not None
    return _RiskProfileProposal(
        profile=RiskProfile.STANDARD,
        rationale=reason,
        minimum_profile=RiskProfile.STANDARD,
        low_admitted=False,
        source_counter_signals=source_counter_signals,
    )


class _RiskProfileDuplicateJsonKeyError(ValueError):
    """Raised when the closed classifier response repeats an object key."""


def _reject_duplicate_risk_profile_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build one classifier-response object only when every key is unique."""
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise _RiskProfileDuplicateJsonKeyError(key)
        parsed[key] = value
    return parsed


def _parse_risk_profile_json(raw: object, source_text: str) -> _RiskProfileProposal:
    """Parse a closed classifier response, admitting ``low`` conservatively."""
    fallback = _standard_risk_profile_proposal(_RISK_PROFILE_FALLBACK_RATIONALE)
    if not isinstance(raw, str):
        return fallback
    text = raw.strip()
    if not text.startswith("{") or not text.endswith("}"):
        return fallback
    try:
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_risk_profile_keys)
    except (json.JSONDecodeError, _RiskProfileDuplicateJsonKeyError):
        return fallback
    if not isinstance(parsed, dict) or set(parsed) != {"tier", "rationale", "evidence"}:
        return fallback
    tier = parsed.get("tier")
    rationale = _one_line_text(parsed.get("rationale"))
    evidence = parsed.get("evidence")
    if tier not in (RiskProfile.LOW.value, RiskProfile.STANDARD.value) or rationale is None:
        return fallback
    if not isinstance(evidence, dict) or set(evidence) != _RISK_PROFILE_EVIDENCE_KEYS:
        return fallback
    if tier == RiskProfile.STANDARD.value:
        if any(value is not None for value in evidence.values()):
            return fallback
        return _standard_risk_profile_proposal(rationale)

    excerpts: dict[str, str] = {}
    for key in _RISK_PROFILE_EVIDENCE_KEYS:
        excerpt = evidence[key]
        if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in source_text:
            return fallback
        excerpts[key] = excerpt
    rationale_lowered = rationale.lower()
    if not (
        _risk_profile_has_affirmative_deletion(rationale)
        and "consumer" in rationale_lowered
        and any(word in rationale_lowered for word in _RISK_PROFILE_SURFACE_WORDS)
        and _low_evidence_matches_admission(excerpts)
    ):
        return fallback
    if _risk_profile_source_counter_signals(rationale):
        return fallback
    signals = _risk_profile_source_counter_signals(source_text)
    if signals:
        return _standard_risk_profile_proposal(
            "Risk classification defaults to standard because the seed names "
            f"{', '.join(signals)}.",
            source_counter_signals=tuple(signals),
        )
    return _RiskProfileProposal(
        profile=RiskProfile.LOW,
        rationale=rationale,
        minimum_profile=RiskProfile.LOW,
        low_admitted=True,
        source_counter_signals=(),
    )


def _propose_risk_profile_from_seed(
    source_text: Optional[str],
    invoker: ClaudeInvoker,
    *,
    slug: str,
    predicted_plan_path: Path,
    repo_root: Path,
    resume: bool,
    allow_resume: bool,
    run_logger: Optional[RunLoggerLike] = None,
) -> _RiskProfileProposal:
    """Classify a single-plan seed without allowing an unavailable model to block create."""
    if source_text is None or not source_text.strip():
        return _standard_risk_profile_proposal(
            "Risk classification defaults to standard because no seed source was supplied."
        )

    prompt = _render_risk_profile_prompt(source_text)
    input_hash = _risk_profile_input_hash(
        source_text, predicted_plan_path, prompt
    )
    ckpt_path = checkpoint_path(repo_root, slug, _RISK_PROFILE_CHECKPOINT_NAME)
    cached = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if resume and allow_resume
        else None
    )
    if cached is not None:
        if run_logger is not None:
            run_logger.checkpoint_hit(
                _RISK_PROFILE_CHECKPOINT_NAME,
                input_hash,
                len(cached.payload.encode("utf-8")),
            )
        return _parse_risk_profile_json(cached.payload, source_text)

    if run_logger is not None:
        run_logger.claude_call_start(
            phase=_RISK_PROFILE_PHASE,
            attempt=1,
            prompt_bytes=len(prompt.encode("utf-8")),
            prompt_sha256=hash_prompt(prompt),
        )
        run_logger.install_call_end_sink(phase=_RISK_PROFILE_PHASE, attempt=1)
    try:
        raw = invoker(prompt)
    except Exception as exc:
        tool(
            f"risk classification invoker failed ({type(exc).__name__}: {exc}); "
            "defaulting to standard"
        )
        return _standard_risk_profile_proposal(
            "Risk classification defaults to standard because the classifier was unavailable."
        )
    finally:
        if run_logger is not None:
            run_logger.uninstall_call_end_sink()
    if not isinstance(raw, str):
        return _standard_risk_profile_proposal(
            "Risk classification defaults to standard because the classifier returned an invalid response."
        )
    proposal = _parse_risk_profile_json(raw, source_text)
    if proposal.rationale == _RISK_PROFILE_FALLBACK_RATIONALE:
        return proposal
    try:
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=input_hash,
                payload=raw,
                created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            ),
        )
    except OSError as exc:
        tool(
            f"failed to save risk-classification checkpoint {ckpt_path} ({exc}); "
            "resume on next run will not be available for this phase"
        )
    else:
        if run_logger is not None:
            run_logger.checkpoint_save(
                _RISK_PROFILE_CHECKPOINT_NAME,
                input_hash,
                len(raw.encode("utf-8")),
            )
    return proposal


_RISK_PROFILE_ORDER = {
    RiskProfile.LOW: 0,
    RiskProfile.STANDARD: 1,
    RiskProfile.HIGH: 2,
}
_RISK_DECLARATION_PHASE_NAME = "resolve_risk_declaration"
_INTERACTIVE_RISK_DECISION_MODES = frozenset({"accepted", "override", "declined"})


def _normalize_risk_profile_proposal(
    proposal: _RiskProfileProposal,
) -> _RiskProfileProposal:
    """Validate step 2's private proposal before a declaration can use it."""
    if not isinstance(proposal, _RiskProfileProposal):
        raise CreateError("risk classifier returned a proposal outside its closed contract")
    if not isinstance(proposal.profile, RiskProfile) or not isinstance(
        proposal.minimum_profile, RiskProfile
    ):
        raise CreateError("risk classifier returned a proposal outside its closed contract")
    if proposal.profile not in {
        RiskProfile.LOW,
        RiskProfile.STANDARD,
    } or proposal.minimum_profile not in {
        RiskProfile.LOW,
        RiskProfile.STANDARD,
    }:
        raise CreateError("risk classifier returned a proposal outside its closed contract")
    if _RISK_PROFILE_ORDER[proposal.profile] < _RISK_PROFILE_ORDER[proposal.minimum_profile]:
        raise CreateError("risk classifier proposed a tier below its own minimum")
    if (
        not isinstance(proposal.low_admitted, bool)
        or not isinstance(proposal.source_counter_signals, tuple)
        or not all(isinstance(signal, str) and signal for signal in proposal.source_counter_signals)
    ):
        raise CreateError("risk classifier returned malformed admission state")
    if proposal.profile is RiskProfile.LOW and (
        not proposal.low_admitted or proposal.source_counter_signals
    ):
        raise CreateError("risk classifier attempted low without its required admission")
    if proposal.profile is RiskProfile.STANDARD and (
        proposal.minimum_profile is not RiskProfile.STANDARD or proposal.low_admitted
    ):
        raise CreateError("risk classifier returned inconsistent standard admission state")
    rationale = _one_line_text(proposal.rationale)
    if rationale is None:
        return _standard_risk_profile_proposal(_RISK_PROFILE_FALLBACK_RATIONALE)
    return _RiskProfileProposal(
        profile=proposal.profile,
        rationale=rationale,
        minimum_profile=proposal.minimum_profile,
        low_admitted=proposal.low_admitted,
        source_counter_signals=proposal.source_counter_signals,
    )


def _risk_declaration_input_hash(
    source_text: str,
    predicted_plan_path: Path,
    proposal: _RiskProfileProposal,
) -> str:
    """Hash every input that makes an interactive declaration replay safe."""
    return compute_input_hash(
        {
            "source_text": source_text,
            "predicted_plan_target": str(predicted_plan_path.resolve()),
            "proposal": {
                "profile": proposal.profile.value,
                "rationale": proposal.rationale,
                "minimum_profile": proposal.minimum_profile.value,
                "low_admitted": proposal.low_admitted,
                "source_counter_signals": list(proposal.source_counter_signals),
            },
            "decision_mode": "interactive",
        }
    )


def _serialize_risk_declaration(declaration: _RiskDeclaration) -> str:
    """Encode a reviewed declaration without allowing an opaque payload shape."""
    return json.dumps(
        {
            "profile": declaration.profile.value,
            "rationale": declaration.rationale,
            "mode": declaration.mode,
        },
        sort_keys=True,
    )


def _declined_risk_declaration(proposal: _RiskProfileProposal) -> _RiskDeclaration:
    """Return the sole declaration payload for declining a proposal."""
    return _RiskDeclaration(
        RiskProfile.STANDARD,
        f"Risk declaration uses standard because the operator declined the proposed {proposal.profile.value} tier.",
        "declined",
    )


def _deserialize_risk_declaration(
    payload: str, proposal: _RiskProfileProposal
) -> Optional[_RiskDeclaration]:
    """Decode only a complete, still-bounded interactive checkpoint payload."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict) or set(decoded) != {"profile", "rationale", "mode"}:
        return None
    try:
        profile = RiskProfile(decoded["profile"])
    except (TypeError, ValueError):
        return None
    rationale = _one_line_text(decoded.get("rationale"))
    mode = decoded.get("mode")
    if (
        rationale is None
        or mode not in _INTERACTIVE_RISK_DECISION_MODES
        or _RISK_PROFILE_ORDER[profile] < _RISK_PROFILE_ORDER[proposal.minimum_profile]
    ):
        return None
    if profile is RiskProfile.LOW and (
        not proposal.low_admitted or proposal.source_counter_signals
    ):
        return None
    if mode == "accepted" and (
        profile is not proposal.profile or rationale != proposal.rationale
    ):
        return None
    if mode == "declined" and _RiskDeclaration(profile, rationale, mode) != _declined_risk_declaration(
        proposal
    ):
        return None
    return _RiskDeclaration(profile=profile, rationale=rationale, mode=mode)


def _silent_risk_declaration(*, source_present: bool, yes: bool) -> _RiskDeclaration:
    """Return the explicit standard declaration used when no decision can occur."""
    if not source_present:
        rationale = "Risk declaration uses standard because no source was supplied."
    elif yes:
        rationale = (
            "Risk declaration uses standard because --yes does not accept model risk proposals."
        )
    else:
        rationale = (
            "Risk declaration uses standard because no interactive operator decision is available."
        )
    return _RiskDeclaration(RiskProfile.STANDARD, rationale, "silent_standard")


def _stdin_has_pending_input() -> bool:
    """Tell whether stdin can report a TTY action or EOF without blocking."""
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
    except (OSError, TypeError, ValueError):
        return False
    return bool(ready)


def _print_risk_declaration_proposal(proposal: _RiskProfileProposal) -> None:
    """Show the proposed tier, rationale, and floor before an operator decides."""
    print("Risk declaration proposal:")
    print(f"  proposed tier: {proposal.profile.value}")
    print(f"  rationale: {proposal.rationale}")
    print(f"  minimum permitted tier: {proposal.minimum_profile.value}")


def _choose_risk_declaration(
    proposal: _RiskProfileProposal,
    *,
    input_fn: InputFn,
    initial_action: Optional[str] = None,
) -> Optional[_RiskDeclaration]:
    """Ask one operator to accept, override, or decline the bounded proposal."""
    while True:
        if initial_action is None:
            _print_risk_declaration_proposal(proposal)
            try:
                action = (
                    input_fn("Risk declaration [a]ccept/[o]verride/[d]ecline to standard [a]: ")
                    .strip()
                    .lower()
                )
            except EOFError:
                return None
        else:
            action, initial_action = initial_action, None
        if not action or action in {"a", "accept"}:
            return _RiskDeclaration(proposal.profile, proposal.rationale, "accepted")
        if action in {"d", "decline"}:
            return _declined_risk_declaration(proposal)
        if action in {"o", "override"}:
            break
        print("choose accept, override, or decline")

    permitted = [
        profile
        for profile in (RiskProfile.LOW, RiskProfile.STANDARD, RiskProfile.HIGH)
        if _RISK_PROFILE_ORDER[profile] >= _RISK_PROFILE_ORDER[proposal.minimum_profile]
    ]
    allowed = "/".join(profile.value for profile in permitted)
    while True:
        try:
            chosen = input_fn(f"Final risk tier [{allowed}]: ").strip().lower()
        except EOFError:
            return None
        try:
            profile = RiskProfile(chosen)
        except ValueError:
            print(f"choose one of: {allowed}")
            continue
        if profile not in permitted:
            print(f"choose one of: {allowed}")
            continue
        while True:
            try:
                rationale = input_fn("Final risk rationale (one line): ")
            except EOFError:
                return None
            normalized_rationale = _one_line_text(rationale)
            if normalized_rationale is None:
                print("a non-empty one-line rationale is required")
                continue
            return _RiskDeclaration(profile, normalized_rationale, "override")


def _resolve_risk_declaration(
    proposal: _RiskProfileProposal,
    *,
    source_text: Optional[str],
    slug: str,
    predicted_plan_path: Path,
    repo_root: Path,
    input_fn: InputFn,
    yes: bool,
    resume: bool,
    allow_resume: bool,
    run_logger: Optional[RunLoggerLike],
) -> _RiskDeclaration:
    """Turn a classifier proposal into the declaration written with a new plan."""
    proposal = _normalize_risk_profile_proposal(proposal)
    source_counter_signals = _risk_profile_source_counter_signals(source_text or "")
    if proposal.profile is RiskProfile.LOW and source_counter_signals:
        raise CreateError(
            "risk classifier attempted low despite source counter-signals: "
            + ", ".join(source_counter_signals)
        )
    source_present = bool(source_text and source_text.strip())
    interactive = source_present and not yes and sys.stdin.isatty()
    started = time.monotonic()
    if run_logger is not None:
        run_logger.phase_start(
            _RISK_DECLARATION_PHASE_NAME,
            proposal={
                "profile": proposal.profile.value,
                "rationale": proposal.rationale,
                "minimum_profile": proposal.minimum_profile.value,
            },
        )

    def finish(declaration: _RiskDeclaration, *, replayed: bool = False) -> _RiskDeclaration:
        if run_logger is not None:
            run_logger.phase_end(
                _RISK_DECLARATION_PHASE_NAME,
                int((time.monotonic() - started) * 1000),
                "ok",
                decision_mode=declaration.mode,
                checkpoint_replayed=replayed,
                final_declaration={
                    "profile": declaration.profile.value,
                    "rationale": declaration.rationale,
                },
            )
        return declaration

    if not interactive:
        return finish(_silent_risk_declaration(source_present=source_present, yes=yes))

    input_hash = _risk_declaration_input_hash(source_text or "", predicted_plan_path, proposal)
    ckpt_path = checkpoint_path(repo_root, slug, _RISK_DECLARATION_CHECKPOINT_NAME)
    initial_action: Optional[str] = None
    if resume and allow_resume:
        cached = load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if cached is not None:
            if _stdin_has_pending_input():
                _print_risk_declaration_proposal(proposal)
                try:
                    initial_action = input_fn(
                        "Risk declaration [a]ccept/[o]verride/[d]ecline to standard [a]: "
                    ).strip().lower()
                except EOFError:
                    return finish(
                        _eof_default(
                            "risk declaration",
                            _silent_risk_declaration(source_present=True, yes=False),
                        )
                    )
            else:
                restored = _deserialize_risk_declaration(cached.payload, proposal)
                if restored is not None:
                    age = _checkpoint_age_minutes(cached)
                    print(f"Resuming cached risk declaration (~{age}m old):")
                    print(f"  tier: {restored.profile.value}")
                    print(f"  rationale: {restored.rationale}")
                    if run_logger is not None:
                        run_logger.checkpoint_hit(
                            _RISK_DECLARATION_CHECKPOINT_NAME,
                            input_hash,
                            len(cached.payload.encode("utf-8")),
                        )
                    return finish(restored, replayed=True)

    chosen = _choose_risk_declaration(
        proposal, input_fn=input_fn, initial_action=initial_action
    )
    if chosen is None:
        return finish(
            _eof_default(
                "risk declaration",
                _silent_risk_declaration(source_present=True, yes=False),
            )
        )
    payload = _serialize_risk_declaration(chosen)
    try:
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=input_hash,
                payload=payload,
                created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            ),
        )
    except OSError as exc:
        if run_logger is not None:
            run_logger.phase_end(
                _RISK_DECLARATION_PHASE_NAME,
                int((time.monotonic() - started) * 1000),
                "error",
                decision_mode=chosen.mode,
                error_class=type(exc).__name__,
            )
        raise CreateError(
            f"failed to save risk-declaration checkpoint {ckpt_path} ({exc}); "
            "plan publication did not begin"
        ) from exc
    if run_logger is not None:
        run_logger.checkpoint_save(
            _RISK_DECLARATION_CHECKPOINT_NAME,
            input_hash,
            len(payload.encode("utf-8")),
        )
    return finish(chosen)


def _parse_depends_on_notes_from_item(
    item: dict, depends_on: list[int]
) -> tuple[dict[int, str], bool]:
    """Parse optional ``depends_on_notes``; sanitize keys and drop empties."""
    if "depends_on_notes" not in item:
        return {}, False
    raw = item.get("depends_on_notes")
    if not isinstance(raw, dict):
        return {}, True
    allowed = set(depends_on)
    notes: dict[int, str] = {}
    ambiguous_keys: set[int] = set()
    for k, v in raw.items():
        key = coerce_response_id(k)
        if key is None:
            continue
        if not isinstance(v, str):
            continue
        stripped = v.strip()
        if not stripped:
            continue
        if key not in allowed or key in ambiguous_keys:
            continue
        if key in notes:
            del notes[key]
            ambiguous_keys.add(key)
        else:
            notes[key] = stripped
    return notes, True


def _parse_steps_json(
    raw: str,
    *,
    rationales_out: Optional[dict[int, str]] = None,
    depends_on_notes_key_present_out: Optional[dict[int, bool]] = None,
) -> Optional[list[Step]]:
    items = _STEP_PROPOSAL_RESPONSE_CONTRACT.decode(raw)
    if not isinstance(items, list) or not items:
        return None
    steps: list[Step] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return None
        step_text = {key: item[key] for key in ("description", "title") if key in item}
        if not step_text or any(
            not isinstance(value, str) or not value.strip()
            for value in step_text.values()
        ):
            return None
        complexity: Optional[Complexity] = None
        raw_cx = item.get("complexity")
        if isinstance(raw_cx, str) and raw_cx:
            try:
                complexity = Complexity(raw_cx)
            except ValueError:
                return None
        # ``change_type`` is deliberately the OPPOSITE of ``complexity``
        # above: an absent key, JSON null, non-string value, or
        # unrecognized string all coerce to ``None`` and the loop
        # continues — never rejecting the whole proposal, never guessing.
        # (``complexity`` returns ``None`` for the entire list on a bad
        # value.) The step contract phrase "unknown/missing values left
        # None, never guessed silently" only makes sense stated against
        # the sibling field that does the opposite.
        change_type: Optional[ChangeType] = None
        raw_ct = item.get("change_type")
        if isinstance(raw_ct, str):
            try:
                change_type = ChangeType(raw_ct)
            except ValueError:
                change_type = None
        # ``rationale`` (the per-step purity defense the prompt requests)
        # has no ``Step`` slot. When the caller supplies ``rationales_out``,
        # capture the non-empty one-liner keyed by step id so the review gate
        # can show claude's reasoning beside the proposal; otherwise it is
        # tolerated and dropped.
        if rationales_out is not None:
            raw_rationale = item.get("rationale")
            if isinstance(raw_rationale, str) and raw_rationale.strip():
                rationales_out[i] = raw_rationale.strip()
        # ``intent`` is a soft field like ``change_type``: absent,
        # null, non-string, or whitespace-only coerces to ``None`` and the loop
        # continues. Deliberately makes NO usability judgment — a ``TODO`` is
        # stored verbatim, because ``is_usable_intent`` is applied in exactly
        # one place (``propose_steps_from_claude``'s retry check) and a second
        # screen here would be a second definition of what counts.
        # Collapsed to one line like every other intent writer: the fence
        # renderer collapses on render, so storing a multi-line value here would
        # make the frontmatter and the rendered fence differ — and a real
        # newline could put a ``##`` at line start inside a block the prompt
        # labels authoritative. Normalization, not validation: nothing is
        # truncated or rejected for its shape.
        raw_intent = item.get("intent")
        intent = (
            collapse_intent_to_one_line(raw_intent)
            if isinstance(raw_intent, str) and raw_intent.strip()
            else None
        )
        files = item.get("files") or []
        creates = item.get("creates") or []
        raw_depends_on = item.get("depends_on") or []
        concept_ids = item.get("concept_ids", [])
        if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
            return None
        if not isinstance(creates, list) or not all(
            isinstance(x, str) for x in creates
        ):
            return None
        if not isinstance(raw_depends_on, list):
            return None
        # Models can emit a quoted numeral despite the response contract's
        # bare-integer form. Preserve an otherwise valid proposal when that
        # string converts cleanly; reject every other string.
        depends_on: list[int] = []
        for x in raw_depends_on:
            dependency_id = coerce_response_id(x)
            if dependency_id is None:
                return None
            depends_on.append(dependency_id)
        depends_on = list(dict.fromkeys(depends_on))
        if not isinstance(concept_ids, list) or not all(
            isinstance(x, str) for x in concept_ids
        ):
            return None
        # ``create`` no longer asks the model for a ``gate:`` list (see
        # ``suggest-gates`` for post-build, grounded gate suggestion instead),
        # so any stray ``gate`` key in the response is ignored rather than
        # written unreviewed onto the step.
        depends_on_notes, notes_key_present = _parse_depends_on_notes_from_item(
            item, depends_on
        )
        if depends_on_notes_key_present_out is not None:
            depends_on_notes_key_present_out[i] = notes_key_present
        try:
            steps.append(
                Step(
                    id=i,
                    **step_text,
                    intent=intent,
                    complexity=complexity,
                    change_type=change_type,
                    files=files,
                    creates=creates,
                    concept_ids=concept_ids,
                    depends_on=depends_on,
                    depends_on_notes=depends_on_notes,
                )
            )
        except PydanticValidationError:
            return None
    return steps or None


def _seed_initial_step_status(steps: list[Step]) -> list[Step]:
    """Promote the first runnable step to ``current`` on initial plan creation.

    Every create entry path (canonical extract, claude propose, interactive
    prompt) builds steps with the schema default ``pending``. A freshly
    authored plan with no ``current`` step leaves ``plan-tool run`` and
    ``review`` without an anchor for "next thing to do" — ``review`` flags
    it explicitly ("step 1 status should be `current` ..."). Pick the
    first step in list order with no ``depends_on`` and mark it
    ``current`` so a new plan lands in a runnable state.

    Idempotent: if any step already has a non-``pending`` status, do
    nothing — the caller has set lifecycle state deliberately and we
    don't override it.
    """
    if any(s.status != StepStatus.PENDING for s in steps):
        return steps
    for i, step in enumerate(steps):
        if not step.depends_on:
            return [
                s.model_copy(update={"status": StepStatus.CURRENT}) if j == i else s
                for j, s in enumerate(steps)
            ]
    return steps


# Sentinel returned by ``_ask_change_type`` when the operator chooses
# ``(s)plit``. A dedicated object (not ``None`` / not a ``ChangeType``) so the
# review loop can tell "reject-and-decompose" apart from "accept the proposal
# verbatim" (``None`` when unproposed) and from a concrete override.
_SPLIT = object()


def _granularity_split_hints(steps: list[Step]) -> dict[int, list[str]]:
    """Map ``step_id`` → deterministic ``granularity-split`` hint lines.

    Builds a throwaway :class:`Plan` from ``steps`` and runs the no-Claude
    granularity advisor (``invoker=None`` is the structural guarantee that no
    subprocess is spawned at the create stage), keeping only
    ``granularity-split`` recs — the one source the review loop's ``(s)plit``
    action can act on. ``granularity-merge`` recs are dropped (no interactive
    merge action here; step 4's completeness audit surfaces merge advice).

    Best-effort: a step list that cannot form a valid :class:`Plan` (e.g. an
    as-yet-unvalidated ``depends_on`` graph) yields ``{}`` rather than a
    traceback — the hint is a convenience and must never break create.
    """
    try:
        plan = Plan(
            title="dry-run",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=steps,
        )
        recs = assess_granularity(
            plan, stage="create", evidence=GranularityEvidence(), invoker=None
        )
    except Exception:
        return {}
    hints: dict[int, list[str]] = {}
    for rec in recs:
        if rec.source != GRANULARITY_SPLIT_SOURCE:
            continue
        line = (
            f"{confidence_label(rec.confidence)} — "
            f"{rec.suggested_action or rec.title or rec.body}"
        )
        hints.setdefault(rec.step_id, []).append(line)
    return hints


def _candidate_fingerprint(steps: list[Step]) -> str:
    payload = [s.model_dump(mode="json", exclude_none=True) for s in steps]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _create_decision_code_fingerprint(
    steps: list[Step],
    *,
    repo_root: Optional[Path],
    output_dir: Optional[Path],
    slug: Optional[str],
) -> Optional[dict[str, str]]:
    """Best-effort ``code_fingerprint`` for the create-review step set.

    ``code_fingerprint`` (the current on-disk bytes of the files these steps
    declare) is the meaningful create-time join anchor: create decisions are
    made *before* the plan is written, so ``plan_fingerprint`` is intentionally
    left empty — a not-yet-written plan digests to a useless constant. Returns
    ``None`` when any of ``repo_root``/``output_dir``/``slug`` is missing, or on
    any compute error, so a fingerprint failure never perturbs the wizard.
    """
    if repo_root is None or output_dir is None or slug is None:
        return None
    try:
        from plan_tool.fingerprint import compute_code_fingerprint

        plan = Plan(
            title="dry-run",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=steps,
        )
        # ``plan_path`` only excludes plan-owned paths (markdown + detail files)
        # from the watched set; those aren't in-scope pre-write anyway, so any
        # plausible path works — no need to thread ``priority`` for the prefix.
        plan_path = output_dir / f"{slug}.md"
        return compute_code_fingerprint(plan, plan_path, repo_root)
    except Exception:
        return None


def _record_create_assessment(
    steps: list[Step],
    *,
    mode: str,
    assessment_id: str,
    can_split: bool,
    repo_root: Optional[Path],
    plan_slug: Optional[str],
    code_fingerprint: Optional[dict[str, str]] = None,
) -> bool:
    if repo_root is None:
        return False
    try:
        plan = Plan(
            title="dry-run",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=steps,
        )
        recs = assess_granularity(
            plan, stage="create", evidence=GranularityEvidence(), invoker=None
        )
        split_recs = [r for r in recs if r.source == GRANULARITY_SPLIT_SOURCE]
        merge_recs = [r for r in recs if r.source == GRANULARITY_MERGE_SOURCE]
        split_ids = {r.step_id for r in split_recs if r.step_id is not None}
        split_step_ids = [str(s.id) for s in steps if s.id in split_ids]
        predicate_counts: dict[str, int] = {}
        for rec in split_recs:
            key = split_predicate_key(rec)
            if key in DETERMINISTIC_SPLIT_PREDICATE_KEYS:
                predicate_counts[key] = predicate_counts.get(key, 0) + 1
        file_footprint = len({path for step in steps for path in step.all_files})
        return record_create_granularity_assessment(
            repo_root,
            plan_slug=plan_slug or "",
            assessment_id=assessment_id,
            steps=len(steps),
            candidate_fingerprint=_candidate_fingerprint(steps),
            file_footprint=file_footprint,
            split=len(split_recs),
            split_steps=len(split_ids),
            merge=len(merge_recs),
            split_step_ids=split_step_ids,
            predicate_counts=predicate_counts,
            can_split=can_split,
            mode=mode,
            code_fingerprint=code_fingerprint,
        )
    except Exception:
        return False


def _record_step_outcome(
    step: Step,
    *,
    action: str,
    assessment_id: Optional[str],
    had_split_hint: bool,
    resolved: Optional[ChangeType],
    repo_root: Optional[Path],
    plan_slug: Optional[str],
    before_steps: Optional[int] = None,
    after_steps: Optional[int] = None,
    error_class: Optional[str] = None,
) -> None:
    if repo_root is None or not assessment_id:
        return
    try:
        proposed_change_type = step.change_type.value if step.change_type else None
        resolved_change_type = resolved.value if isinstance(resolved, ChangeType) else None
        record_create_step_outcome(
            repo_root,
            plan_slug=plan_slug or "",
            assessment_id=assessment_id,
            step_id=str(step.id),
            had_split_hint=had_split_hint,
            action=action,
            proposed_change_type=proposed_change_type,
            resolved_change_type=resolved_change_type,
            before_steps=before_steps,
            after_steps=after_steps,
            error_class=error_class,
        )
    except Exception:
        return


def _format_depends_on_review_lines(
    step: Step, steps_by_id: dict[int, Step]
) -> list[str]:
    """Return unprefixed review lines for one step's outbound ``depends_on`` edges."""
    if not step.depends_on:
        return []
    lines: list[str] = []
    for dep_id in step.depends_on:
        note = step.depends_on_notes.get(dep_id)
        antecedent = steps_by_id.get(dep_id)
        if antecedent is not None:
            base = f"depends_on {dep_id} ({antecedent.title})"
        else:
            base = f"depends_on {dep_id}"
        if note:
            lines.append(f"{base}: {note}")
        else:
            lines.append(base)
    return lines


def _ask_change_type(
    input_fn: InputFn,
    *,
    step: Step,
    proposed: Optional[ChangeType],
    rationale: Optional[str],
    can_split: bool,
    granularity_hint: Optional[list[str]] = None,
    all_steps: Optional[list[Step]] = None,
):
    """Prompt the operator to confirm / override / split one step's change type.

    Returns the resolved ``ChangeType`` (override), ``proposed`` verbatim
    (Enter — which is ``None`` when the step carries no proposal, an honest
    unset rather than a guessed default), or the :data:`_SPLIT` sentinel when
    the operator asks to decompose a mixed step. ``(s)plit`` is only offered
    and accepted when ``can_split`` (a claude invoker is available).

    The empty answer is handled inline rather than routed through ``_ask`` /
    ``_ask_choice``: ``_ask_choice`` returns its ``default`` on empty input
    (a guess) and ``_ask(required=True)`` spins on a no-default prompt — both
    the opposite of "Enter means accept, even when there's nothing proposed."
    """
    proposed_label = proposed.value if proposed is not None else "unproposed"
    print(f"step {step.id}: {step.title}")
    print(f"  proposed change_type: {proposed_label}")
    if all_steps is not None:
        steps_by_id = {s.id: s for s in all_steps}
        for line in _format_depends_on_review_lines(step, steps_by_id):
            print(f"  {line}")
    if rationale:
        print(f"  rationale: {rationale}")
    for line in granularity_hint or ():
        print(f"  granularity: {line}")
    options = "(r)efactor / (f)eature / (n)on-code / "
    if can_split:
        options += "(s)plit / "
    options += "Enter to accept"
    while True:
        raw = input_fn(f"  {options}: ").strip().lower()
        if raw == "":
            return proposed
        if raw == "r":
            return ChangeType.REFACTOR
        if raw == "f":
            return ChangeType.FEATURE
        if raw == "n":
            return ChangeType.NON_CODE
        if raw == "s":
            if can_split:
                return _SPLIT
            print("split unavailable (no claude invoker); choose r, f, n, or Enter")
            continue
        valid = "r, f, n, s, or Enter" if can_split else "r, f, n, or Enter"
        print(f"please choose {valid}")


def _propose_step_split(
    step: Step,
    invoker: ClaudeInvoker,
    *,
    repo_root: Optional[Path] = None,
    run_logger: Optional[Any] = None,
) -> Optional[list[Step]]:
    """Ask claude to decompose one mixed step into a refactor + feature pair.

    Returns exactly two replacement :class:`Step`s — the refactor half first,
    the feature half second — reusing the same JSON shape ``_parse_steps_json``
    reads (so ``change_type`` + ``rationale`` ride the existing parse). Returns
    ``None`` on an unparseable or wrong-length response; the caller leaves the
    original step unchanged and re-prompts.

    The replacement steps' ``depends_on`` are *not* trusted here —
    :func:`_apply_step_split` sets them deterministically (refactor inherits
    the original's edges, feature depends on the refactor half).
    """
    prompt = (
        "You are decomposing ONE implementation step that mixes "
        "behavior-preserving refactoring with new behavior. Split it into "
        "exactly TWO type-pure steps: a `refactor` step (make the change "
        "easy) FIRST, then a `feature` step (make the easy change) SECOND. "
        "Each step's code must be as purely one type as possible; each "
        "rationale must defend that purity.\n\n"
        f"Step title: {step.title}\n"
        f"Step files: {', '.join(step.all_files) or '(none)'}\n"
        f"Step detail: {step.detail or '(none)'}\n\n"
        f"Step concept_ids: {json.dumps(step.concept_ids)}\n\n"
        "Return ONLY a JSON array of exactly two objects, each with keys "
        '`description`, `change_type` ("refactor" then "feature"), `files`, '
        "`creates`, `concept_ids`, and a one-line `rationale`. Distribute "
        "only the supplied concept_ids: every supplied id must appear on at "
        "least one replacement, no new id may appear, and an id may appear "
        "on both replacements. Do not include `depends_on` or "
        "`depends_on_notes` — dependency wiring is handled "
        "deterministically by the caller."
    )
    # Phase matches the caller's ``phase_start("propose_step_split")`` so the
    # call's cost lands inside the phase that brackets it; without a sink the
    # call is spent but unrecorded (see BACKLOG #176-#178).
    raw = logged_invoke(
        invoker,
        prompt,
        run_logger=run_logger,
        phase="propose_step_split",
        attempt=1,
        step_id=step.id,
    )
    local_rationales: dict[int, str] = {}
    parsed = _parse_steps_json(raw, rationales_out=local_rationales)
    if parsed is None or len(parsed) != 2:
        return None
    if set(step.concept_ids) != {
        concept_id
        for replacement in parsed
        for concept_id in replacement.concept_ids
    }:
        return None
    return parsed


# Finding sources whose ``apply_finding`` edit is a prose/body-section fill
# that cannot change the steps/references re-proposal input (``title +
# description``). A round that applied only these can skip the re-proposal.
_PROSE_ONLY_APPLY_SOURCES = frozenset({"body-completeness", "detail-body"})


def _reproposal_is_skippable(applied_sources: set[str]) -> bool:
    """True when every finding applied this iteration round was a prose/
    body-section edit that cannot change the steps/references re-proposal
    input. Empty set returns False -- no signal means re-propose (the
    conservative default). See :data:`_PROSE_ONLY_APPLY_SOURCES`."""
    return bool(applied_sources) and applied_sources <= _PROSE_ONLY_APPLY_SOURCES


def _unanimous_depends_on_note(notes: list[str | None]) -> str | None:
    """Return the shared note when every voter agrees; else ``None`` (omit)."""
    if not notes:
        return None
    unique = set(notes)
    if len(unique) != 1:
        return None
    return notes[0]


def _remap_depends_on_notes(
    notes: dict[int, str],
    depends_on: list[int],
    *,
    id_map: dict[int, int] | None = None,
    remap_key: Callable[[int], int] | None = None,
    drop_source_keys: frozenset[int] = frozenset(),
) -> dict[int, str]:
    """Remap note keys; keep only keys present in ``depends_on``."""
    if (id_map is None) == (remap_key is None):
        raise ValueError("exactly one of id_map or remap_key is required")

    def _key(old: int) -> int:
        if remap_key is not None:
            return remap_key(old)
        assert id_map is not None
        return id_map.get(old, old)

    dep_set = set(depends_on)
    out: dict[int, str] = {}
    for old_key, note in notes.items():
        if old_key in drop_source_keys:
            continue
        new_key = _key(old_key)
        if new_key in dep_set:
            out[new_key] = note
    return out


def _build_merged_outbound_depends_on_notes(
    steps: list[Step],
    merge_set: set[int],
    renumber: dict[int, int],
    merged_deps: list[int],
) -> dict[int, str]:
    """Unanimous outbound notes for the merged survivor's external edges."""
    external_antecedents: set[int] = set()
    for s in steps:
        if s.id in merge_set:
            for d in s.depends_on:
                if d not in merge_set:
                    external_antecedents.add(d)

    out: dict[int, str] = {}
    dep_set = set(merged_deps)
    for antecedent_id in external_antecedents:
        voters = [
            s for s in steps if s.id in merge_set and antecedent_id in s.depends_on
        ]
        notes = [s.depends_on_notes.get(antecedent_id) for s in voters]
        unanimous = _unanimous_depends_on_note(notes)
        if unanimous is not None:
            new_key = renumber[antecedent_id]
            if new_key in dep_set:
                out[new_key] = unanimous
    return out


def _collapse_inbound_depends_on_notes(
    step: Step,
    renumber: dict[int, int],
    new_depends_on: list[int],
) -> dict[int, str]:
    """Collapse inbound notes when several old edges fold onto one survivor."""
    groups: dict[int, list[int]] = {}
    for d in step.depends_on:
        groups.setdefault(renumber[d], []).append(d)

    out: dict[int, str] = {}
    dep_set = set(new_depends_on)
    for new_d, old_ids in groups.items():
        if new_d not in dep_set:
            continue
        if len(old_ids) == 1:
            old_id = old_ids[0]
            if old_id in step.depends_on_notes:
                out[new_d] = step.depends_on_notes[old_id]
        else:
            notes = [step.depends_on_notes.get(oid) for oid in old_ids]
            unanimous = _unanimous_depends_on_note(notes)
            if unanimous is not None:
                out[new_d] = unanimous
    return out


def _apply_step_split(
    steps: list[Step], target_id: int, replacements: list[Step]
) -> list[Step]:
    """Splice ``replacements`` in place of step ``target_id`` and rewire edges.

    Pure list→list transform (no I/O). The result satisfies seven invariants:

    1. Ids are contiguous ``1..N`` after the splice (every step renumbered by
       position).
    2. The first replacement inherits the target's ``depends_on``.
    3. The second replacement depends on the first (refactor-before-feature).
    4. Any step that depended on the target repoints to the *terminal*
       replacement (the split's final half), never a vanished id.
    5. Edges into steps after the insertion point shift by
       ``len(replacements) - 1``.
    6. The first replacement inherits the target's ``status`` (later halves
       ``PENDING``), so splitting the ``current`` step keeps exactly one
       current step. Callers pass status-less replacements; this owns it — do
       not pre-set replacement statuses. (``DONE`` targets are blocked upstream
       by ``split_is_safe``, so a ``DONE`` status never reaches here.)
    7. The union of replacement ``concept_ids`` exactly equals the target's
       concept-id set. An id may be repeated across replacements, but none may
       be dropped or invented.

    The spliced list is validated by constructing a dry-run :class:`Plan`;
    a malformed graph raises :class:`CreateError` carrying
    :func:`_summarize_step_graph_error`'s message and leaves the input list
    untouched (the function never mutates ``steps``).
    """
    pos = next((i for i, s in enumerate(steps) if s.id == target_id), None)
    if pos is None:
        raise CreateError(f"split target step {target_id} not found")
    target_concept_ids = set(steps[pos].concept_ids)
    replacement_concept_ids = {
        concept_id
        for replacement in replacements
        for concept_id in replacement.concept_ids
    }
    if replacement_concept_ids != target_concept_ids:
        dropped = sorted(target_concept_ids - replacement_concept_ids)
        invented = sorted(replacement_concept_ids - target_concept_ids)
        problems: list[str] = []
        if dropped:
            problems.append(f"dropped concept_ids: {', '.join(dropped)}")
        if invented:
            problems.append(f"invented concept_ids: {', '.join(invented)}")
        raise CreateError(
            "split replacements must exactly conserve target concept_ids ("
            + "; ".join(problems)
            + ")"
        )
    shift = len(replacements) - 1
    terminal_new_id = pos + len(replacements)  # id of the last replacement

    def remap(old_id: int) -> int:
        # Steps before the insertion keep their position (and 1-based id);
        # the target's id folds into the terminal replacement; everything
        # after the target shifts down by ``shift``.
        if old_id < target_id:
            return old_id
        if old_id == target_id:
            return terminal_new_id
        return old_id + shift

    rewired: list[Step] = []
    new_id = 1
    for i, s in enumerate(steps):
        if i == pos:
            for j, rep in enumerate(replacements):
                if j == 0:
                    new_deps = [remap(d) for d in steps[pos].depends_on]
                    # The first half inherits the target's lifecycle status so
                    # splitting the ``current`` step keeps exactly one current
                    # step; later halves are pending. (A DONE target is blocked
                    # upstream by ``split_is_safe``, so it never reaches here.)
                    new_status = steps[pos].status
                else:
                    new_deps = [new_id - 1]  # depend on the previous replacement
                    new_status = StepStatus.PENDING
                rewired.append(
                    rep.model_copy(
                        update={
                            "id": new_id,
                            "depends_on": new_deps,
                            "depends_on_notes": {},
                            "status": new_status,
                        }
                    )
                )
                new_id += 1
            continue
        new_deps = [remap(d) for d in s.depends_on]
        rewired.append(
            s.model_copy(
                update={
                    "id": new_id,
                    "depends_on": new_deps,
                    "depends_on_notes": _remap_depends_on_notes(
                        s.depends_on_notes,
                        new_deps,
                        remap_key=remap,
                        drop_source_keys=frozenset({target_id}),
                    ),
                }
            )
        )
        new_id += 1

    try:
        Plan(
            title="dry-run",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=rewired,
        )
    except PydanticValidationError as exc:
        raise CreateError(
            f"split produced an invalid step graph: {_summarize_step_graph_error(exc)}"
        ) from exc
    return rewired


def _apply_step_merge(
    steps: list[Step], merge_ids: list[int], merged: Step
) -> list[Step]:
    """Fold ``merge_ids`` into the single ``merged`` step and rewire edges.

    The structural inverse of :func:`_apply_step_split`: it collapses a
    contiguous, dependency-connected set of step ids into one survivor,
    renumbers the surviving steps to contiguous ``1..N``, repoints every
    edge, and validates the result by constructing a dry-run :class:`Plan`.

    The transform trusts ``merged`` for authored content (title, ``files``,
    ``creates``, ``change_type``, …) and owns its ``id``, ``depends_on``,
    ``status``, and ``concept_ids`` — the mirror of how
    :func:`_apply_step_split` trusts the proposer for content but owns the
    edges (and the first half's status). Concept ownership is the ordered,
    deduplicated union of the folded members; placeholder-only ownership is
    ignored. The survivor inherits ``current`` iff any member was current
    (else ``PENDING``), so folding the current step keeps exactly one current
    step. The merged step inherits the
    union of the set's *external* ``depends_on`` (edges among set members are
    dropped); every step that depended on any member repoints to the one
    survivor id (collapsed duplicates deduped).

    Pure list→list transform: it builds a fresh list via ``model_copy`` and
    never mutates ``steps`` or ``merged``. A bad set (fewer than two ids, a
    missing id, a gapped run, a disjoint set) or a collapse that produces a
    malformed graph (e.g. a cycle) raises :class:`CreateError` with the input
    untouched. Cycle/dangling detection is single-sourced in the dry-run
    :class:`Plan` validator — no parallel ``graphlib`` check is added.
    """
    merge_set = set(merge_ids)
    if len(merge_set) < 2:
        raise CreateError("merge requires at least two step ids")
    existing = {s.id for s in steps}
    missing = next((i for i in merge_set if i not in existing), None)
    if missing is not None:
        raise CreateError(f"merge target step {missing} not found")
    lo, hi = min(merge_set), max(merge_set)
    if sorted(merge_set) != list(range(lo, hi + 1)):
        raise CreateError(
            "merge set must be a contiguous run of step ids (no gaps)"
        )

    # Dependency-connected: treat member→member edges as undirected and
    # require the set to be one connected component. A fork/join among
    # members is connected and accepted; a disjoint set is rejected.
    adjacency: dict[int, set[int]] = {i: set() for i in merge_set}
    for s in steps:
        if s.id in merge_set:
            for d in s.depends_on:
                if d in merge_set:
                    adjacency[s.id].add(d)
                    adjacency[d].add(s.id)
    reached: set[int] = set()
    frontier = [lo]
    while frontier:
        node = frontier.pop()
        if node in reached:
            continue
        reached.add(node)
        frontier.extend(adjacency[node] - reached)
    if reached != merge_set:
        raise CreateError(
            "merge set is not dependency-connected (disjoint) — cannot fold "
            "unambiguously"
        )

    # Explicit old→new renumber map from a single position-walk. Every member
    # folds to the survivor's id (allocated when the first member is seen);
    # non-members take the next sequential id. A merge has several removal
    # points that all collapse to one survivor, so no positional closed-form
    # (split's ``remap``) stays correct — the dict is the single source of
    # truth. Because the set is contiguous and ids start contiguous, this
    # yields ``merged_new_id == lo`` and steps ``> hi`` shifted down by
    # ``hi - lo`` (``len(set) - 1``).
    renumber: dict[int, int] = {}
    next_id = 0
    merged_new_id: Optional[int] = None
    for s in steps:
        if s.id in merge_set:
            if merged_new_id is None:
                next_id += 1
                merged_new_id = next_id
            renumber[s.id] = merged_new_id
        else:
            next_id += 1
            renumber[s.id] = next_id

    # Merged step's depends_on: union over all members of their external
    # edges, remapped and deduped (intra-set edges dropped). No external dep
    # can remap to ``merged_new_id`` (a dep ``< lo`` stays ``< lo``; a dep
    # ``> hi`` lands above it), so a self-loop is structurally impossible.
    merged_deps: list[int] = []
    for s in steps:
        if s.id in merge_set:
            for d in s.depends_on:
                if d not in merge_set:
                    merged_deps.append(renumber[d])
    merged_deps = list(dict.fromkeys(merged_deps))
    merged_depends_on_notes = _build_merged_outbound_depends_on_notes(
        steps, merge_set, renumber, merged_deps
    )

    # Concept ownership is structural merge state, not caller-authored
    # placeholder content. Walk members in plan order and their ids in authored
    # order, retaining the first occurrence of each id. This both conserves all
    # member ownership and prevents the placeholder from inventing ownership.
    merged_concept_ids = list(
        dict.fromkeys(
            concept_id
            for s in steps
            if s.id in merge_set
            for concept_id in s.concept_ids
        )
    )

    def _remap_external(deps: list[int]) -> list[int]:
        # Dependents of any member collapse onto the one survivor id; dedup
        # preserving order so a step that depended on two members keeps a
        # single edge (the dry-run Plan does not reject duplicate edges).
        return list(dict.fromkeys(renumber[d] for d in deps))

    # The survivor inherits ``current`` iff any member was current, so a merge
    # that folds the current step keeps exactly one current step (the merge
    # analog of ``_apply_step_split``'s first-half status inheritance). A DONE
    # member is blocked upstream by ``_merge_is_safe``, so members are only
    # PENDING/CURRENT here; the transform owns status just as split does.
    merged_status = (
        StepStatus.CURRENT
        if any(s.status == StepStatus.CURRENT for s in steps if s.id in merge_set)
        else StepStatus.PENDING
    )

    rewired: list[Step] = []
    emitted_merged = False
    for s in steps:
        if s.id in merge_set:
            if not emitted_merged:
                rewired.append(
                    merged.model_copy(
                        update={
                            "id": merged_new_id,
                            "depends_on": merged_deps,
                            "depends_on_notes": merged_depends_on_notes,
                            "status": merged_status,
                            "concept_ids": merged_concept_ids,
                        }
                    )
                )
                emitted_merged = True
            continue
        new_deps = _remap_external(s.depends_on)
        rewired.append(
            s.model_copy(
                update={
                    "id": renumber[s.id],
                    "depends_on": new_deps,
                    "depends_on_notes": _collapse_inbound_depends_on_notes(
                        s, renumber, new_deps
                    ),
                }
            )
        )

    try:
        Plan(
            title="dry-run",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=rewired,
        )
    except PydanticValidationError as exc:
        raise CreateError(
            f"merge produced an invalid step graph: {_summarize_step_graph_error(exc)}"
        ) from exc
    return rewired


def _review_step_change_types(
    steps: list[Step],
    *,
    input_fn: InputFn,
    invoker: Optional[ClaudeInvoker],
    repo_root: Optional[Path] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    resume: bool = True,
    run_logger: Optional[RunLoggerLike] = None,
    yes: bool = False,
    rationales: Optional[dict[int, str]] = None,
) -> list[Step]:
    """Operator decision gate over a finalized step list (the create wizard's
    confirm / override / split loop).

    Runs over whatever ``steps`` list ``create_plan`` assembled — claude
    proposal, canonical import, or interactive fallback — so it is the single
    classification gate for every source. Returns the reviewed list.

    Behavior by mode:

    - ``resume`` + a matching ``create-step-review`` checkpoint → the stored
      post-review list is restored without prompting (answers survive a
      checkpoint/resume).
    - ``yes`` → proposals are accepted verbatim and every still-unproposed
      step id is named in a single stderr note (the step-7 purity probe is the
      documented backstop for a mixed proposal that slips through unreviewed).
    - non-interactive stdin → proposals accepted verbatim, silently (no
      operator to prompt; mirrors the resume-confirmation TTY gate).
    - interactive → each step's proposal + rationale is shown and the operator
      confirms / overrides / splits; the reviewed list is checkpointed.
    """
    rationales = rationales or {}

    # Association creation happens outside the best-effort recorder, so guard
    # it explicitly. Without a fresh non-empty id this pass emits no create
    # telemetry rather than persisting unjoinable or fabricated rows.
    try:
        assessment_id: Optional[str] = uuid.uuid4().hex or None
    except Exception:
        assessment_id = None

    # Compute the create-time ``code_fingerprint`` once per review pass for the
    # assessment. Outcomes carry only the smaller association. Best-effort
    # (``None`` on missing inputs or any error; computed ``{}`` stays distinct).
    code_fp = _create_decision_code_fingerprint(
        steps, repo_root=repo_root, output_dir=output_dir, slug=slug
    )

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _step_review_input_hash(slug, steps, output_dir, repo_root)
        ckpt_path = checkpoint_path(repo_root, slug, _STEP_REVIEW_CHECKPOINT_NAME)

    # Resume: a saved post-review list short-circuits the prompts entirely,
    # keyed on the pre-review proposal so a changed proposal invalidates it.
    if resume and ckpt_path is not None and input_hash is not None:
        cached = load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if cached is not None:
            restored = _deserialize_reviewed_steps(cached.payload)
            if restored is not None:
                if run_logger is not None:
                    run_logger.checkpoint_hit(
                        _STEP_REVIEW_CHECKPOINT_NAME,
                        input_hash,
                        len(cached.payload.encode("utf-8")),
                    )
                if assessment_id is not None:
                    _record_create_assessment(
                        steps,
                        mode=CREATE_MODE_CHECKPOINT,
                        assessment_id=assessment_id,
                        can_split=invoker is not None,
                        repo_root=repo_root,
                        plan_slug=slug,
                        code_fingerprint=code_fp,
                    )
                return restored

    # ``--yes``: no operator to confirm or split. Accept proposals verbatim
    # and name the still-unproposed steps on stderr.
    if yes:
        if assessment_id is not None:
            _record_create_assessment(
                steps,
                mode=CREATE_MODE_YES,
                assessment_id=assessment_id,
                can_split=invoker is not None,
                repo_root=repo_root,
                plan_slug=slug,
                code_fingerprint=code_fp,
            )
        unproposed = [s.id for s in steps if s.change_type is None]
        if unproposed:
            ids = ", ".join(str(i) for i in unproposed)
            tool(
                f"--yes: {len(unproposed)} step(s) left unclassified "
                f"(change_type=None): {ids}; the completeness purity probe is "
                "the backstop for any mixed step that slipped through",
                level="note",
            )
        return steps

    # No operator attached (CI / piped / tests whose stdin is not a TTY):
    # keep proposals verbatim rather than blocking on ``input()``. Mirrors
    # the resume-confirmation TTY gate in ``propose_steps_from_claude``.
    if not sys.stdin.isatty():
        if assessment_id is not None:
            _record_create_assessment(
                steps,
                mode=CREATE_MODE_NON_TTY,
                assessment_id=assessment_id,
                can_split=invoker is not None,
                repo_root=repo_root,
                plan_slug=slug,
                code_fingerprint=code_fp,
            )
        return steps

    can_split = invoker is not None
    assessment_recorded = bool(
        assessment_id
        and _record_create_assessment(
            steps,
            mode=CREATE_MODE_INTERACTIVE,
            assessment_id=assessment_id,
            can_split=can_split,
            repo_root=repo_root,
            plan_slug=slug,
            code_fingerprint=code_fp,
        )
    )
    outcome_assessment_id = assessment_id if assessment_recorded else None
    reviewed: list[Step] = list(steps)
    i = 0
    while i < len(reviewed):
        step = reviewed[i]
        # Recompute per iteration: a ``(s)plit`` renumbers every step id, so a
        # map keyed on pre-split ids would point at the wrong step afterward.
        # Only when ``can_split`` — the nudge is toward the (s)plit action, so
        # it is noise when the operator cannot act on it.
        hint_map = _granularity_split_hints(reviewed) if can_split else {}
        answer = _ask_change_type(
            input_fn,
            step=step,
            proposed=step.change_type,
            rationale=rationales.get(step.id),
            can_split=can_split,
            granularity_hint=hint_map.get(step.id),
            all_steps=reviewed,
        )
        had_split_hint = bool(hint_map.get(step.id))
        if answer is _SPLIT:
            _record_step_outcome(
                step,
                action=CREATE_ACTION_SPLIT_REQUESTED,
                assessment_id=outcome_assessment_id,
                had_split_hint=had_split_hint,
                resolved=None,
                repo_root=repo_root,
                plan_slug=slug,
            )
            if run_logger is not None:
                run_logger.phase_start("propose_step_split")
            split_t0 = time.monotonic()
            split_outcome = "ok"
            try:
                replacements = _propose_step_split(
                    step, invoker, repo_root=repo_root, run_logger=run_logger
                )
            except Exception as exc:
                split_outcome = "error"
                _record_step_outcome(
                    step,
                    action=CREATE_ACTION_SPLIT_ERROR,
                    assessment_id=outcome_assessment_id,
                    had_split_hint=had_split_hint,
                    resolved=None,
                    repo_root=repo_root,
                    plan_slug=slug,
                    error_class=type(exc).__name__,
                )
                raise
            finally:
                if run_logger is not None:
                    run_logger.phase_end(
                        "propose_step_split",
                        int((time.monotonic() - split_t0) * 1000),
                        split_outcome,
                    )
            if replacements is None:
                _record_step_outcome(
                    step,
                    action=CREATE_ACTION_SPLIT_UNUSABLE,
                    assessment_id=outcome_assessment_id,
                    had_split_hint=had_split_hint,
                    resolved=None,
                    repo_root=repo_root,
                    plan_slug=slug,
                )
                tool(
                    f"step {step.id}: split proposal was unusable; "
                    "leaving the step as-is — re-answer to retry or override",
                    level="note",
                )
                continue  # re-prompt the same step
            before_steps = len(reviewed)
            try:
                reviewed = _apply_step_split(reviewed, step.id, replacements)
            except CreateError as exc:
                _record_step_outcome(
                    step,
                    action=CREATE_ACTION_SPLIT_INVALID,
                    assessment_id=outcome_assessment_id,
                    had_split_hint=had_split_hint,
                    resolved=None,
                    repo_root=repo_root,
                    plan_slug=slug,
                    error_class="CreateError",
                )
                tool(f"step {step.id}: {exc}", level="warning")
                continue  # keep the pre-split list, re-prompt the same step
            _record_step_outcome(
                step,
                action=CREATE_ACTION_SPLIT_APPLIED,
                assessment_id=outcome_assessment_id,
                had_split_hint=had_split_hint,
                resolved=None,
                repo_root=repo_root,
                plan_slug=slug,
                before_steps=before_steps,
                after_steps=len(reviewed),
            )
            # Show the deterministic remap before continuing the review.
            print(f"split step {step.id} into:")
            steps_by_id = {s.id: s for s in reviewed}
            for r in reviewed:
                ct = r.change_type.value if r.change_type else "unproposed"
                print(f"  step {r.id}: {r.title} [{ct}]")
                for line in _format_depends_on_review_lines(r, steps_by_id):
                    print(f"  {line}")
            # Re-review the two new halves: leave ``i`` pointing at the
            # refactor half so both re-enter the loop with their proposals.
            continue
        if step.change_type is None and answer is None:
            action = CREATE_ACTION_UNCLASSIFIED_ACCEPTED
        elif step.change_type is None and isinstance(answer, ChangeType):
            action = CREATE_ACTION_UNCLASSIFIED_CLASSIFIED
        elif answer == step.change_type:
            action = CREATE_ACTION_ACCEPT
        else:
            action = CREATE_ACTION_OVERRIDE
        _record_step_outcome(
            step,
            action=action,
            assessment_id=outcome_assessment_id,
            had_split_hint=had_split_hint,
            resolved=answer if isinstance(answer, ChangeType) else None,
            repo_root=repo_root,
            plan_slug=slug,
        )
        reviewed[i] = step.model_copy(update={"change_type": answer})
        i += 1

    # Persist the reviewed list so a resume skips the prompts. Best-effort:
    # a disk error here shouldn't abort an otherwise-successful create.
    if ckpt_path is not None and input_hash is not None:
        payload = json.dumps(
            [s.model_dump(mode="json", exclude_none=True) for s in reviewed]
        )
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=payload,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save step-review checkpoint {ckpt_path} ({exc}); "
                "resume on next run will re-prompt for step change types"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _STEP_REVIEW_CHECKPOINT_NAME,
                    input_hash,
                    len(payload.encode("utf-8")),
                )
    return reviewed


def _deserialize_reviewed_steps(payload: str) -> Optional[list[Step]]:
    """Rebuild the reviewed step list from a ``create-step-review`` payload.

    Returns ``None`` when the payload can't be decoded into valid steps, so a
    corrupt checkpoint falls through to a fresh review rather than crashing.
    """
    try:
        items = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or not items:
        return None
    try:
        return [Step(**item) for item in items]
    except (TypeError, PydanticValidationError):
        return None


def _serialize_intent_review(plan: Plan) -> str:
    """JSON payload for the ``create-intent`` checkpoint: both altitudes."""
    return json.dumps(
        {
            "intent": plan.intent,
            "steps": [
                s.model_dump(mode="json", exclude_none=True) for s in plan.steps
            ],
        }
    )


def _deserialize_intent_review(
    payload: str,
) -> Optional[tuple[Optional[str], list[Step]]]:
    """Rebuild ``(plan intent, steps)`` from a ``create-intent`` payload.

    Returns ``None`` when the payload can't be decoded, so a corrupt checkpoint
    falls through to a fresh offer rather than crashing. The step half is
    re-encoded and handed to :func:`_deserialize_reviewed_steps` so both
    checkpoints validate steps through one decoder.
    """
    try:
        record = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    intent = record.get("intent")
    if intent is not None and not isinstance(intent, str):
        return None
    steps = _deserialize_reviewed_steps(json.dumps(record.get("steps")))
    return None if steps is None else (intent, steps)


def _intent_review_input_hash(
    slug: str,
    plan: Plan,
    output_dir: Path,
    repo_root: Path,
    *,
    project_context: str = "",
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached intent review.

    The step-review digest (slug + steps + output dir), plan-level ``intent``,
    and any confirmed project context decide which targets are asked about, so
    a re-mapped ``## Outcome``, changed step list, or changed scope boundary
    never replays stale accept / decline answers.
    """
    payload: dict[str, object] = {
        "steps": _step_review_input_hash(slug, plan.steps, output_dir, repo_root),
        "plan_intent": plan.intent,
    }
    if project_context:
        payload["project_context"] = project_context
    return compute_input_hash(payload)


def _offer_missing_intents(
    plan: Plan,
    *,
    input_fn: InputFn,
    invoker: ClaudeInvoker,
    source_text: str = "",
    repo_root: Optional[Path] = None,
    slug: Optional[str] = None,
    output_dir: Optional[Path] = None,
    resume: bool = True,
    run_logger: Optional[RunLoggerLike] = None,
    yes: bool = False,
) -> Plan:
    """Operator decision gate offering an ``intent`` wherever one is missing.

    Runs after :func:`_review_create_concepts`: the step ids are final there
    (:func:`_review_step_change_types` renumbers on a split) and the plan is
    still only in memory, so accepted values ride the single initial
    ``write_new_plan`` instead of a write-then-rewrite.

    ``review.is_usable_intent`` alone decides which targets are missing, so a
    plan or step already carrying a usable value is never asked about and can
    never be overwritten. Presence is the only test applied to a draft — see
    :mod:`plan_tool.intent_proposal`.

    Behavior by mode:

    - nothing missing → ``plan`` comes back untouched; no round-trip, no
      prompt, no checkpoint.
    - ``resume`` + a matching ``create-intent`` checkpoint → the stored
      post-review values are restored without re-proposing.
    - ``yes`` → every draft is accepted verbatim and the targets are named in
      one stderr note. An intent is inert prose (not an executable command),
      and ``--yes`` already means "take every prompt default" — the draft
      walk's default is accept.
    - non-TTY stdin without ``yes`` → skipped silently before the call, which
      is what keeps the extra round-trip strictly opt-in.
    - interactive → accept / edit / decline each draft.

    An unusable or empty proposal leaves the intents unset and never fails the
    create (:func:`propose_references_from_claude`'s precedent). Every skip
    carries a ``skip_reason`` so ``runs show`` reports which arm was taken.
    """
    started = time.monotonic()
    if run_logger is not None:
        run_logger.phase_start(_INTENT_PHASE_NAME)

    def end_phase(outcome: str, **extra: object) -> None:
        if run_logger is not None:
            run_logger.phase_end(
                _INTENT_PHASE_NAME,
                int((time.monotonic() - started) * 1000),
                outcome,
                **extra,
            )

    plan_needs_intent = not is_usable_intent(plan.intent)
    step_ids = [s.id for s in plan.steps if not is_usable_intent(s.intent)]
    project_context = _project_context_block(repo_root)
    if not plan_needs_intent and not step_ids:
        end_phase("skipped", skip_reason="nothing_missing")
        return plan

    ckpt_path: Optional[Path] = None
    input_hash: Optional[str] = None
    if slug is not None and output_dir is not None and repo_root is not None:
        input_hash = _intent_review_input_hash(
            slug, plan, output_dir, repo_root, project_context=project_context
        )
        ckpt_path = checkpoint_path(repo_root, slug, _INTENT_REVIEW_CHECKPOINT_NAME)

    if resume and ckpt_path is not None and input_hash is not None:
        cached = load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if cached is not None:
            restored = _deserialize_intent_review(cached.payload)
            if restored is not None:
                if run_logger is not None:
                    run_logger.checkpoint_hit(
                        _INTENT_REVIEW_CHECKPOINT_NAME,
                        input_hash,
                        len(cached.payload.encode("utf-8")),
                    )
                end_phase("ok")
                return plan.model_copy(
                    update={"intent": restored[0], "steps": restored[1]}
                )

    # Non-TTY (CI / piped / tests) without ``--yes``: no operator to offer to.
    if not yes and not sys.stdin.isatty():
        end_phase("skipped", skip_reason="non_interactive")
        return plan

    drafts = propose_intents(
        plan,
        invoker=invoker,
        plan_needs_intent=plan_needs_intent,
        step_ids=step_ids,
        source_text=source_text,
        project_context=project_context,
        run_logger=run_logger,
    )
    if drafts is None:
        end_phase("skipped", skip_reason="unusable_response")
        return plan

    if yes:
        kept = list(drafts)
        if kept:
            named = ", ".join(
                "the plan" if d.step_id is None else f"step {d.step_id}"
                for d in kept
            )
            tool(f"--yes: accepted the proposed intent for {named}", level="note")
    else:
        kept = review_intent_drafts(drafts, input_fn=input_fn)

    # A full decline is a *decision* and checkpoints like any other: without it
    # the resume re-spends the proposal round-trip and re-asks every question
    # already answered. An empty ``drafts`` is NOT that — the model simply
    # produced nothing, so there is no decision to freeze, and checkpointing it
    # would leave the plan permanently intent-less with no create-time remedy
    # (the input hash does not move, so every later --resume short-circuits).
    reviewed = apply_intent_drafts(plan, kept) if kept else plan
    decided = bool(drafts)

    if decided and ckpt_path is not None and input_hash is not None:
        payload = _serialize_intent_review(reviewed)
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=payload,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save intent checkpoint {ckpt_path} ({exc}); resume "
                "on next run will re-propose and re-ask for intents"
            )
        else:
            if run_logger is not None:
                run_logger.checkpoint_save(
                    _INTENT_REVIEW_CHECKPOINT_NAME,
                    input_hash,
                    len(payload.encode("utf-8")),
                )

    if not kept:
        end_phase("skipped", skip_reason="all_declined")
        return plan
    end_phase("ok")
    return reviewed


def _preserve_on_disk_step_fields(
    proposed: Step,
    prior: Optional[Step],
    *,
    proposal_included_depends_on_notes: bool = False,
) -> Step:
    """Merge one re-proposed step onto its on-disk twin (``prior``).

    Fields that outlive the ``--iterate`` loop's step re-proposal:

    - ``status`` — ``propose_steps_from_claude`` can return ``status: done``
      from its reading of the codebase, which is wrong here; transitions belong
      to ``plan-tool run``, not the create authoring flow. An in-flight
      ``current`` or already-``done`` step keeps its state.
    - ``intent`` — a usable value already on the step was reviewed by the
      operator at :func:`_offer_missing_intents`, so it **wins over** whatever
      a later automated pass returns, carrying an intent or not.
    - ``depends_on_notes`` — when the proposal JSON **omits** the key and the
      step title is unchanged, on-disk notes are preserved intersected with the
      proposal's ``depends_on``. When the proposal **includes** the key (even
      as ``{}``), the proposal's value wins.
    - ``gate`` — the proposal never carries one (``create`` does not propose
      gates; see :func:`_parse_steps_json`), so a title-matched step's on-disk
      commands (set by ``suggest-gates`` or through a direct edit) are always preserved
      rather than reproposed away.

    **``prior`` is matched by position, not identity.** Ids come from
    ``_parse_steps_json``'s ``enumerate``, and the re-proposal runs from
    scratch, so a round that inserts, drops, or reorders steps puts a
    *different* step under the same id. Carrying an intent across that is a
    false statement about the step it lands on — and the fence threads it into
    that step's detail and run prompts under an authoritative heading, which is
    exactly what ``intent_proposal.parse_intent_drafts`` refuses to do when the
    backend mis-targets a draft. Title equality is the identity check: same id
    *and* same title, or the value does not travel. ``status`` keeps its
    pre-existing id-only keying (see BACKLOG #226).

    A step the proposal newly adds has no ``prior``: it starts ``pending``
    (nothing brand-new can legitimately be ``done`` during create) and keeps
    whatever intent it came with — ``review.check_intent_presence`` covers the
    empty case from there.
    """
    update: dict[str, object] = {
        "status": prior.status if prior is not None else StepStatus.PENDING
    }
    if (
        prior is not None
        and prior.title == proposed.title
        and is_usable_intent(prior.intent)
    ):
        update["intent"] = prior.intent
    if (
        not proposal_included_depends_on_notes
        and prior is not None
        and prior.title == proposed.title
        and prior.depends_on_notes
    ):
        allowed = set(proposed.depends_on)
        preserved = {
            k: v for k, v in prior.depends_on_notes.items() if k in allowed
        }
        update["depends_on_notes"] = preserved
    if prior is not None and prior.title == proposed.title and prior.gate:
        update["gate"] = prior.gate
    return proposed.model_copy(update=update)


def predict_plan_path(
    output_dir: Path,
    slug: str,
    priority: Priority,
) -> Path:
    """Compute where :func:`write_new_plan` would land a plan, without writing.

    Used to know the new plan's path *before* the write actually happens
    — specifically so collision archival can prepend an accurate
    "Replaced by ..." notice. The prefix is always the priority bucket
    (1=high, 2=medium, 3=low), so the predicted path depends only on
    ``slug`` and ``priority``.
    """
    return output_dir / f"{PRIORITY_PREFIX[priority]}-{slug}.md"


def _reject_empty_concept_headings(sections: Sequence[BodySection]) -> None:
    """Refuse a section whose name is empty after normalization.

    ``concept_id`` rejects an empty name with a bare ``ValueError`` that names
    no heading. ``parse_body_sections`` already strips whitespace before
    dropping trailing ``:``/``.``, so a name is empty exactly when the id
    derivation would raise.
    """
    empty = [f"'## {section.heading}'" for section in sections if not section.name]
    if empty:
        raise CreateError(
            "plan body has section headings with no name after normalization "
            "(surrounding whitespace and trailing ':' and '.' are dropped): "
            f"{', '.join(empty)}. Give each a name or remove it, and retry."
        )


def _reject_repeated_concept_headings(
    sections: Sequence[BodySection], tree: ConceptTree
) -> None:
    """Refuse sections that share a concept id (it hashes the section name).

    The scope check would otherwise fail with a hash-based message that names
    no heading. Names are normalized (case, spacing, trailing ``:``/``.``,
    Unicode), so the colliding spellings can differ; the message lists each.
    """
    spellings: dict[str, list[str]] = {}
    for section, node in zip(sections, tree.concepts, strict=True):
        spellings.setdefault(node.id, []).append(section.heading)
    groups = [
        ", ".join(f"'## {heading}'" for heading in headings)
        for headings in spellings.values()
        if len(headings) > 1
    ]
    if groups:
        raise CreateError(
            "plan body has sections whose headings are the same after case, "
            f"spacing, trailing ':' or '.', and Unicode normalization: "
            f"{'; '.join(groups)}. Concept review needs one section per "
            "heading. Rename or merge them and retry."
        )


def _review_create_concepts(
    tree: ConceptTree,
    steps: list[Step],
    *,
    input_fn: InputFn,
    yes: bool,
    interactive: Optional[bool] = None,
) -> tuple[ConceptTree, list[Step]]:
    """Gate a lazy deferral, recording only ``defer``/``wont_do`` decisions.

    Returns a flat ``record_kind="decision-record"`` tree holding only the
    deferred nodes (each bucket-tagged with its section) plus ``steps``
    unchanged. Included concepts contribute nothing — a committed step is the
    only proof of ownership. Under ``-y`` a proposed deferral is recorded
    pending (``review_state="unreviewed"``), never auto-signed; interactively
    a confirmed deferral is signed off and a declined one produces no node.
    """
    if interactive is None:
        interactive = sys.stdin.isatty() and not yes
    decisions: dict[str, str] = {}

    for node in tree.concepts:
        suggested_decision = node.decision if node.decision in {
            "include", "defer", "wont_do"
        } else "include"
        decision = suggested_decision
        if interactive:
            answer = _ask(
                input_fn,
                f"Concept '{node.title}' [include/defer/wont_do] "
                f"[{suggested_decision}]: ",
                default=suggested_decision,
            ).strip().lower()
            if answer not in {"include", "defer", "wont_do"}:
                raise CreateError(f"unknown concept decision {answer!r}")
            decision = answer
        decisions[node.id] = decision

    reviewed = review_concept_scope(
        tree,
        [node.id for node in tree.concepts],
        decisions,
        tree.plan_fingerprint,
        sign_off=interactive,
    ) if tree.concepts else tree

    # Only deferrals are recorded, as a flat decision record: the section name
    # becomes the bucket and the hierarchy/section body are dropped so the
    # record is a decision, not a cache. Bootstrap nodes have an empty
    # parent_path, so tagging the bucket satisfies flat-kind validation.
    deferred = [
        ConceptNode(
            id=node.id,
            title=node.title,
            order=node.order,
            decision=node.decision,
            rationale=node.rationale,
            review_state=node.review_state,
            bucket=node.title,
        )
        for node in reviewed.concepts
        if node.decision in {"defer", "wont_do"}
    ]
    record = ConceptTree(
        plan_slug=tree.plan_slug,
        plan_fingerprint=tree.plan_fingerprint,
        concepts=deferred,
        record_kind=RECORD_KIND_DECISION,
    )
    return record, steps


def write_new_plan(
    output_dir: Path,
    slug: str,
    plan: Plan,
    *,
    references: Optional[list[Reference]] = None,
    references_body: Optional[str] = None,
    seed_sections: Optional[dict[str, str]] = None,
    synthesized_sections: Optional[dict[str, Optional[str]]] = None,
    supplied_guardrails: Optional[dict[str, str]] = None,
    direct_source_authority: Optional[_DirectSourceAuthority] = None,
    normalized_preparation_sections: Optional[dict[str, Optional[str]]] = None,
) -> Path:
    """Write ``plan`` to ``<output_dir>/<prefix>-<slug>.md``.

    The filename prefix is the priority bucket: ``1`` for high, ``2``
    for medium, ``3`` for low. Multiple plans with the same priority
    share a prefix; the slug disambiguates them.

    Seeds a minimal stub file and calls ``write_plan``, routing the initial
    serialization through the same code path used for every subsequent edit.

    ``references`` populates the body's ``References`` section with a
    bulleted list of links. ``references_body`` is an explicit complete
    References body and takes precedence over links. Protected source References
    accompany either research representation.

    ``synthesized_sections`` is the highest-precedence body-content
    source; see :func:`_render_plan_body` for the full precedence
    contract (``synthesized`` ≻ ``seed_sections`` ≻ ``_(TODO)_``). Original
    supplied guardrails are the exception: they always render verbatim.
    ``direct_source_authority`` and ``normalized_preparation_sections`` keep
    protected supplied evidence free of generated Testing prose.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = predict_plan_path(output_dir, slug, plan.priority)
    # The stub is deliberately not a structured plan. A failed final
    # serialization is therefore never mistaken for an adoptable plan.
    stub = "---\ncreate_in_progress: true\n---\n" + _render_plan_body(
        plan.title,
        references=references,
        references_body=references_body,
        seed_sections=seed_sections,
        synthesized_sections=synthesized_sections,
        supplied_guardrails=supplied_guardrails,
        steps=plan.steps,
        preserve_source_sections=(
            direct_source_authority is not None
            or normalized_preparation_sections is not None
        ),
    )
    path.write_text(stub, encoding="utf-8")
    # create owns this file during synchronous construction (it just wrote
    # the stub above) — the compare-and-swap guard is for concurrent
    # *external* edits to an existing plan, not create's own two-step
    # stub-then-fill write.
    write_plan(path, plan, expect_unchanged=False)
    return path


def _open_findings_hints(
    slug: str,
    open_count: int,
    *,
    variant: str = "marginal",
) -> list[str]:
    """Next-step hint lines when the loop stops with open findings (or, for
    ``stage_failure``, the same commands in an order suited to the FAILURE
    banner). Shared by the convergence loop's ``marginal`` / budget stop
    banner AND its stage-failure banner so copy cannot drift.

    ``variant``:
    - ``marginal`` — completeness, then reconcile-plan-walk, then detail (matches
      the normal loop-stop hints).
    - ``stage_failure`` — completeness, then detail, then reconcile-plan-walk so
      non-destructive steps precede the ``create`` re-run line the caller
      appends after these hints."""
    if open_count <= 0:
        return []
    completeness = (
        f"  plan-tool completeness {slug}  "
        "# continue refining in place (keeps applied edits, drives open "
        "findings down)"
    )
    review = (
        f"  plan-tool reconcile-plan-walk {slug}   "
        f"# interactively review the {open_count} open finding(s)"
    )
    detail = (
        f"  plan-tool detail {slug}        "
        "# author detail files (resolves 'needs detail' findings)"
    )
    if variant == "stage_failure":
        return [completeness, detail, review]
    return [completeness, review, detail]


def _render_references_body(references: list[Reference]) -> str:
    """Render a ``Reference`` list as the bullet block for a plan body.

    Mirrors the bullet format produced inline by :func:`_render_plan_body`
    so a surgical References patch lands the same shape as a fresh plan.
    Empty list yields the empty string; the caller decides whether to
    patch or skip on empty.
    """
    lines: list[str] = []
    for ref in references:
        bullet = f"- [{ref.title}]({ref.url})"
        if ref.description:
            bullet += f" — {ref.description}"
        lines.append(bullet)
    return "\n".join(lines)


def _patch_plan_body_section(
    plan_path: Path, section_title: str, new_body: str
) -> bool:
    """Replace the body of an H2 section in a plan file in place.

    Restores the iteration-loop's ability to update individual body
    sections after :func:`write_plan` (which preserves the body
    byte-for-byte and so cannot land per-section refreshes on its own).
    The current call site is the References update in :func:`create_plan`;
    other surgical patches can reuse this helper.

    Locates the H2 matching ``section_title`` (case-insensitive) in the
    prose body (post-frontmatter) and replaces everything between the
    heading line and the next H1/H2 (or EOF) with ``new_body``. The
    heading line itself, the frontmatter, and surrounding sections are
    preserved.

    ``new_body`` should be the raw section content without the heading
    line. One blank line is inserted before and after to keep the
    section visually separated.

    Returns ``True`` when the section was found and patched, ``False``
    when no matching H2 exists in the body (no-op). A missing or malformed
    frontmatter fence is treated as no-op rather than raising — the body
    can't be reliably located, so there's nothing safe to patch, but that
    alone isn't evidence the plan is broken. An unmatched opening *code*
    fence anywhere in the text is different and raises ``CreateError``
    instead: it's a real defect in the plan being iterated, worth
    surfacing loudly (matching the iterate loop's own fail-fast guard
    after `apply_finding`) rather than silently patching around it.
    """
    text = plan_path.read_text(encoding="utf-8")

    if not text.startswith("---\n"):
        return False
    second_fence = text.find("\n---\n", 4)
    if second_fence < 0:
        return False
    body_start = second_fence + len("\n---\n")
    body = text[body_start:]

    # Check the same body slice this function actually patches, not a
    # separately-located one: reject_unmatched_create_fence finds the
    # frontmatter boundary its own way (tolerant of trailing whitespace on
    # the closing fence line), which can disagree with the exact-literal
    # boundary search above and validate text this function never patches.
    body_scan = _fenced_code_spans(body)
    if body_scan.unmatched_opening is not None:
        raise CreateError(
            f"{plan_path}: unmatched opening code fence; add a matching "
            "closing fence before authoring."
        )

    target = section_title.strip().lower()
    fenced_spans = body_scan.spans
    matches = [
        match
        for match in _H2_HEADING_RE.finditer(body)
        if not any(start <= match.start() < end for start, end in fenced_spans)
    ]
    for i, m in enumerate(matches):
        if m.group(1) != "##":
            continue
        if m.group(2).strip().lower() != target:
            continue
        section_body_start = m.end()
        section_body_end = (
            matches[i + 1].start() if i + 1 < len(matches) else len(body)
        )
        new_section = f"\n\n{new_body}\n\n" if new_body else "\n\n"
        new_text = (
            text[:body_start]
            + body[:section_body_start]
            + new_section
            + body[section_body_end:]
        )
        plan_path.write_text(new_text, encoding="utf-8")
        return True
    return False


_REFERENCES_FOLLOWING_SECTIONS = frozenset(
    title.lower()
    for title in PLAN_BODY_SECTIONS[PLAN_BODY_SECTIONS.index("References") + 1:]
)


def _references_present(body: str, text: str) -> bool:
    """True when ``body`` appears verbatim in ``text`` as contiguous whole lines.

    Not a substring test (a fragment of unrelated prose must not count) and not
    a per-line merge (a block must never be split): protected References are
    present as a block or restored as a block.
    """
    want = [line.rstrip() for line in body.strip().splitlines()]
    have = [line.rstrip() for line in text.splitlines()]
    return any(
        have[start:start + len(want)] == want
        for start in range(len(have) - len(want) + 1)
    )


def _insert_references_section(plan_path: Path, body: str) -> None:
    """Add a missing ``## References`` section in canonical body order."""
    text = plan_path.read_text(encoding="utf-8")
    body_start = text.find("\n---\n", 4) + len("\n---\n") if text.startswith("---\n") else 0
    scan = _fenced_code_spans(text)
    insert_at = len(text)
    for match in _H2_HEADING_RE.finditer(text, body_start):
        if any(start <= match.start() < end for start, end in scan.spans):
            continue
        if (
            match.group(1) == "##"
            and match.group(2).strip().lower() in _REFERENCES_FOLLOWING_SECTIONS
        ):
            insert_at = match.start()
            break
    head = text[:insert_at].rstrip("\n")
    tail = text[insert_at:]
    plan_path.write_text(
        (head + "\n\n" if head else "")
        + "## References\n\n"
        + body
        + "\n"
        + ("\n" + tail if tail else ""),
        encoding="utf-8",
    )


def _restore_materialized_evidence_sections(
    plan_path: Path,
    normalized_sections: Optional[dict[str, Optional[str]]],
) -> bool:
    """Restore raw-source evidence after a later writer touched plan prose."""
    if normalized_sections is None:
        return False
    changed = False
    for section_name in ("References", *_evidence_only_body_section_keys()):
        body = normalized_sections.get(section_name)
        if body is None:
            continue
        current = extract_h2_sections(
            plan_path.read_text(encoding="utf-8"), ignore_fenced_code=True
        ).get(section_name.lower())
        if section_name == "References" and current and current != "_(TODO)_":
            if _references_present(body, current):
                continue
            body = current + "\n\n" + body
        if current == body:
            continue
        if section_name == "References" and current is None:
            if not _patch_plan_body_section(plan_path, "References", body):
                _insert_references_section(plan_path, body)
            changed = True
            continue
        if not _patch_plan_body_section(plan_path, section_name, body):
            raise CreateError(
                f"validated evidence section {section_name!r} disappeared from {plan_path}"
            )
        changed = True
    return changed


def _restore_materialized_evidence_and_sync_concepts(
    plan_path: Path,
    normalized_sections: Optional[dict[str, Optional[str]]],
    concept_tree: ConceptTree,
    *,
    saved_concepts: Optional[ConceptTree],
) -> bool:
    """Restore protected evidence and keep its concept fingerprint current."""
    if not _restore_materialized_evidence_sections(plan_path, normalized_sections):
        return False
    from plan_tool.review_persistence import compute_plan_fingerprint

    concept_tree.plan_fingerprint = compute_plan_fingerprint(plan_path)
    _persist_or_clear_concepts(
        plan_path,
        concept_tree,
        safe_to_clear=_safe_to_clear_concepts(saved_concepts),
    )
    return True


def _extract_supplied_guardrails(seed_text: Optional[str]) -> dict[str, str]:
    """Return recognized guardrail bodies supplied by the original seed only."""
    sections = extract_h2_sections(seed_text or "", ignore_fenced_code=True)
    return {
        section: sections[section.lower()]
        for section in GUARDRAIL_BODY_SECTIONS
        if section.lower() in sections
    }


def _intent_from_seed_outcome(seed_text: Optional[str]) -> Optional[str]:
    """Map the seed's ``## Outcome`` section to a plan ``intent``, or ``None``.

    Presence is the whole contract — ``review.is_usable_intent`` decides what
    counts, so nothing here re-tests for emptiness or a placeholder. Whitespace
    collapses to single spaces (matching ``scope_fence._render_intent_section``,
    so the stored value is the string the fence emits). The first non-empty
    paragraph alone supplies the intent; thematic-break-only lines are ignored.

    Reads the *raw* seed: ``## Outcome`` is not a canonical plan-body section,
    so the distill first-pass drops it. Frontmatter is stripped first because a
    ``##``-prefixed YAML comment in a canonical source would otherwise shadow
    the real section — see ``scope_fence._strip_frontmatter``.
    """
    sections = extract_h2_sections(
        _strip_frontmatter(seed_text or ""), ignore_fenced_code=True
    )
    outcome = sections.get("outcome")
    if outcome is None:
        return None
    outcome_with_break_boundaries = "\n".join(
        "" if line.strip() in {"---", "***", "___"} else line
        for line in outcome.splitlines()
    )
    first_paragraph = next(
        (
            paragraph
            for paragraph in re.split(r"\n[ \t]*\n", outcome_with_break_boundaries)
            if paragraph.strip()
        ),
        "",
    )
    collapsed = collapse_intent_to_one_line(first_paragraph)
    return collapsed if is_usable_intent(collapsed) else None


def _find_dropped_guardrail_headings(
    supplied_guardrails: dict[str, str],
    retained_guardrail_headings: set[str],
) -> list[str]:
    """Return supplied guardrail headings absent from one lossy-stage output."""
    return [
        heading
        for heading in GUARDRAIL_BODY_SECTIONS
        if heading in supplied_guardrails
        and heading not in retained_guardrail_headings
    ]


def _find_uncarried_guardrail_headings(
    supplied_guardrails: dict[str, str],
    stage_guardrails: dict[str, str],
) -> list[str]:
    """Return non-empty stage-produced guardrails absent from the raw seed."""
    return [
        heading
        for heading in GUARDRAIL_BODY_SECTIONS
        if heading not in supplied_guardrails
        and stage_guardrails.get(heading, "").strip()
    ]


def _warn_dropped_guardrail_headings(
    headings: list[str], *, stage: str
) -> None:
    """Surface advisory findings for supplied guardrail headings a stage omitted."""
    if not headings:
        return
    tool(
        f"{stage} dropped supplied guardrail heading(s); verify the "
        "original constraint was retained:",
        level="warning",
    )
    for heading in headings:
        print(
            f"  - ## {heading} (dropped during {stage})",
            file=sys.stderr,
        )


def _warn_uncarried_guardrail_headings(headings: list[str], *, stage: str) -> None:
    """Warn when a stage recognized a guardrail heading the raw seed did not supply."""
    if not headings:
        return
    tool(
        f"{stage} produced guardrail heading(s) absent from the original "
        "seed; they will not appear in the written plan:",
        level="warning",
    )
    for heading in headings:
        print(f"  - ## {heading}", file=sys.stderr)


# Deliverable-document artifacts that a plan is expected to *produce*.
# When the distilled body *references* one of these in narrative prose
# ("the operator cutover runbook", "the evaluation matrix") but the
# Acceptance criteria never pins it to a verifiable invariant, the
# distill pass likely dropped the content the reference points at while
# keeping the dangling pointer — exactly the failure that loses an
# explicitly-required deliverable during reorganization. Kept tight
# (high-signal artifact nouns) to bound false positives; tune here.
_DROPPED_REF_KEYWORDS: tuple[str, ...] = (
    "runbook",
    "checklist",
    "worksheet",
    "matrix",
    "appendix",
)
# "Section 7", "section 12" — a numbered cross-reference into a document
# the plan owns. Dangling when no acceptance criterion cites that section.
_SECTION_REF_RE = re.compile(r"\bSection\s+\d+\b", re.IGNORECASE)


def _artifact_ref_re() -> re.Pattern[str]:
    """Match an artifact reference: up to 3 leading words + a keyword noun.

    ``operator cutover runbook`` / ``per-vendor evaluation matrix`` /
    a bare ``runbook`` all match; the captured phrase is reported and its
    trailing word is the keyword used for corroboration.
    """
    kws = "|".join(_DROPPED_REF_KEYWORDS)
    return re.compile(
        rf"\b((?:[A-Za-z][\w-]*\s+){{0,3}}(?:{kws}))\b", re.IGNORECASE
    )


@dataclass(frozen=True)
class DroppedReference:
    """A distilled-body reference to a deliverable no acceptance criterion pins.

    ``anchor`` is the matched reference text (``"Section 7"``,
    ``"operator cutover runbook"``); ``section`` is the (lowercased) H2 the
    reference was found in; ``keyword`` is the artifact noun (or
    ``"section"`` for a numbered cross-reference) that triggered the match.

    Advisory only — :func:`create_plan` surfaces these as a warning, never a
    hard failure, because a legitimate pointer to an external doc can match
    the same shape. The signal is "eyeball whether distillation dropped this."
    """

    anchor: str
    section: str
    keyword: str


def find_dropped_references(distilled_markdown: str) -> list[DroppedReference]:
    """Flag references to produced artifacts the distilled plan doesn't pin down.

    Scans every H2 section *except* Acceptance criteria for artifact
    references (``_DROPPED_REF_KEYWORDS`` noun phrases + ``Section N``
    cross-references). A reference is corroborated — and therefore NOT
    flagged — when its keyword (or the literal ``section N``) also appears
    in the Acceptance criteria section, the place a plan pins deliverables
    to verifiable invariants. Uncorroborated references are returned, one
    per distinct artifact, in document order.

    The motivating failure: a distilled plan whose Risks section said "the
    runbook in Section 7 sequences this" while no step or acceptance
    criterion authored that runbook — the distill pass had silently dropped
    an explicitly-required operator-cutover deliverable but kept the
    pointer. Run on the single-plan distill output before it feeds the
    steps / references / body round-trips.
    """
    # strip_fenced_code, not just ignore_fenced_code: a fenced example
    # mentioning a keyword must not corroborate or manufacture a reference.
    # ``extract_h2_sections`` lowercases keys.
    sections = extract_h2_sections(distilled_markdown, strip_fenced_code=True)
    acceptance = sections.get("acceptance criteria", "").lower()
    artifact_re = _artifact_ref_re()
    out: list[DroppedReference] = []
    seen: set[str] = set()
    for name, body in sections.items():
        if name == "acceptance criteria" or not body:
            continue
        for m in artifact_re.finditer(body):
            phrase = re.sub(r"\s+", " ", m.group(1).strip())
            keyword = phrase.rsplit(" ", 1)[-1].lower()
            if keyword in acceptance or keyword in seen:
                continue
            seen.add(keyword)
            out.append(
                DroppedReference(anchor=phrase, section=name, keyword=keyword)
            )
        for m in _SECTION_REF_RE.finditer(body):
            anchor = re.sub(r"\s+", " ", m.group(0))
            dedup = anchor.lower()
            if dedup in acceptance or dedup in seen:
                continue
            seen.add(dedup)
            out.append(
                DroppedReference(anchor=anchor, section=name, keyword="section")
            )
    return out


# Tokens shorter than this are skipped by the spell check -- short tokens in
# slugs/titles are overwhelmingly abbreviations / acronyms (app, ssm, dr, qa)
# that a dictionary would false-flag, and a genuine 3-letter typo in a slug is
# cheap to catch by eye.
_SPELLCHECK_MIN_LEN = 4

# Domain vocabulary a general dictionary doesn't carry. Plan slugs and titles
# are dense with these, and a suggestion like `'jira' -> 'lira'` fires on every
# touch of the plan — noise that trains the operator to ignore the advisory.
# Lowercase; matched case-insensitively. Extend it when a real domain word
# draws a suggestion, rather than muting the check.
_SPELLCHECK_ALLOWLIST = frozenset(
    {
        "jira",
        "backlog",
        "backlogs",
        "repo",
        "repos",
        "frontmatter",
        "changelog",
        "runbook",
        "subcommand",
        "subcommands",
        "reconcile",
        "reconciler",
        "dedupe",
        "dedup",
        "linting",
        "pytest",
        "pyproject",
        "yaml",
        "json",
        "cli",
        "sdk",
        "config",
        "configs",
        "auth",
        "async",
        "namespacing",
        "unstaged",
        "worktree",
        "worktrees",
        "gitignore",
        "gitignored",
        "atlassian",
        "confluence",
        "claude",
        "anthropic",
    }
)


class Speller(Protocol):
    """Minimal spell-checker surface :func:`find_misspellings` needs.

    Lets the default (``pyspellchecker``-backed) engine be swapped for a
    fake in tests, so the spell-check logic is exercised without depending
    on the optional package being installed.
    """

    def is_misspelled(self, word: str) -> bool: ...

    def correction(self, word: str) -> Optional[str]: ...


class _PySpellChecker:
    """Adapter over the optional ``pyspellchecker`` package's ``SpellChecker``."""

    def __init__(self, spell: object) -> None:
        self._spell = spell

    def is_misspelled(self, word: str) -> bool:
        # SpellChecker supports ``in`` against its frequency dictionary.
        return word.lower() not in self._spell  # type: ignore[operator]

    def correction(self, word: str) -> Optional[str]:
        fix = self._spell.correction(word.lower())  # type: ignore[attr-defined]
        if not fix or fix == word.lower():
            return None
        return fix


def _load_speller() -> Optional[Speller]:
    """Build a ``pyspellchecker``-backed :class:`Speller`, or ``None``.

    Optional dependency (``pip install "plan-tool[spell]"``). When the
    package isn't installed the import fails and the slug/title spell check
    degrades to a silent no-op — the feature is opt-in and never breaks a
    base install or costs a single token (it's a local frequency
    dictionary, not an LLM round-trip).
    """
    try:
        from spellchecker import SpellChecker  # type: ignore
    except ImportError:
        return None
    return _PySpellChecker(SpellChecker())


def _looks_like_code(token: str) -> bool:
    """True when ``token`` looks like an identifier / path / acronym, not prose.

    Spell-checking these would drown the signal in false positives, so they
    are skipped: anything carrying path/identifier punctuation, any digit,
    or an uppercase letter past the first character (camelCase like
    ``instanceName`` or an ALL-CAPS acronym like ``SSM``). A plainly
    Title-cased word (``Standardize``) is *not* code — only the first
    character is uppercase.
    """
    if any(ch in token for ch in "/._`@$"):
        return True
    if any(ch.isdigit() for ch in token):
        return True
    if any(ch.isupper() for ch in token[1:]):
        return True
    return False


def _spellcheck_candidates(text: str) -> list[str]:
    """Tokenize ``text`` (a slug or title) into plain words worth checking.

    Splits on whitespace and dashes (so slug words separate), drops
    code-shaped tokens (:func:`_looks_like_code`), strips leading/trailing
    punctuation, and keeps only words of at least
    :data:`_SPELLCHECK_MIN_LEN` characters.
    """
    out: list[str] = []
    for raw in re.split(r"[\s\-]+", text.strip()):
        if not raw or _looks_like_code(raw):
            continue
        word = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", raw)
        if len(word) >= _SPELLCHECK_MIN_LEN:
            out.append(word)
    return out


@dataclass(frozen=True)
class Misspelling:
    """A likely-misspelled word found in a plan's slug or title.

    ``field`` is the source field (``"slug"`` / ``"title"``); ``suggestion``
    is the speller's best correction, or ``None`` when it had none. Advisory
    only — :func:`create_plan` surfaces these as a note, never a hard
    failure, since plan slugs/titles legitimately contain domain coinages.
    """

    word: str
    field: str
    suggestion: Optional[str] = None


def find_misspellings(
    fields: dict[str, str], *, speller: Optional[Speller] = None
) -> list[Misspelling]:
    """Flag likely misspellings in narrow, high-signal plan fields.

    Intended for the ``slug`` and ``title`` only — NOT free-form plan bodies,
    which are dense with jargon, identifiers, and file paths that a
    dictionary would false-flag. Code-shaped and short tokens are skipped
    (see :func:`_looks_like_code` / :func:`_spellcheck_candidates`), as is
    domain vocabulary in :data:`_SPELLCHECK_ALLOWLIST`; the remaining words
    are checked against ``speller`` (default: the optional
    ``pyspellchecker`` engine via :func:`_load_speller`).

    Returns one :class:`Misspelling` per distinct misspelled word, in field
    then document order. Returns ``[]`` — a silent no-op — when the optional
    spell-check dependency isn't installed, so callers need no guard.
    """
    if speller is None:
        speller = _load_speller()
    if speller is None:
        return []
    out: list[Misspelling] = []
    seen: set[str] = set()
    for field_name, text in fields.items():
        if not text:
            continue
        for word in _spellcheck_candidates(text):
            low = word.lower()
            if low in seen or low in _SPELLCHECK_ALLOWLIST:
                continue
            if not speller.is_misspelled(word):
                continue
            seen.add(low)
            out.append(
                Misspelling(
                    word=word,
                    field=field_name,
                    suggestion=speller.correction(word),
                )
            )
    return out


def _canonical_seed_covers_all(seed_sections: dict[str, str]) -> bool:
    """True when every canonical body section is already present in the seed.

    Compared key set is ``{s.lower() for s in PLAN_BODY_SECTIONS} -
    {"steps", "references"}``. ``extract_h2_sections`` already drops
    empty-body H2s, so a positive answer means "synthesis would add
    nothing the H2 extractor doesn't already cover." Used by
    :func:`create_plan` to skip the ``propose_body_sections`` round-trip
    when the seed is canonical.
    """
    required = {s.lower() for s in _canonical_body_section_keys()}
    present = {k.lower() for k in seed_sections.keys()}
    return required.issubset(present)


def validate_from_existing_seed(
    seed_text: str, *, source: Path | str = "--from-existing seed"
) -> FileBackedSourceIntake:
    """Validate and return the file-backed intake facts for compatibility."""
    return classify_file_backed_source(seed_text, source=source)


def _find_placeholder_body_sections(body: str) -> list[str]:
    """Return the H2 section names whose body is the literal ``_(TODO)_``.

    Walks :data:`PLAN_BODY_SECTIONS` minus ``"Steps"`` (which is always
    populated with the frontmatter-pointer one-liner), inspects each
    section's body via :func:`extract_h2_sections`, and returns the
    titles of sections present in ``body`` whose stripped body equals
    ``"_(TODO)_"``. Sections absent from ``body`` are not flagged —
    the helper's contract is "find placeholders that were rendered,"
    not "find every gap in an arbitrary markdown blob." On the
    production call site the input is the candidate body
    :func:`_render_plan_body` is about to write, which always renders
    every section, so the "absent" branch is unreachable there.

    Matches the literal ``"_(TODO)_"`` only. The helper is paired with
    :func:`_render_plan_body`, which only emits that exact form. The
    broader ``review._BODY_PLACEHOLDER_RE`` (which also matches user-
    edited ``TODO`` / ``(TODO)`` variants) is deliberately not reused
    here so prose that incidentally contains the word ``TODO`` (e.g.
    a ``## Deferred`` bullet saying ``TODO: revisit``) doesn't trip
    the wizard's fail-loud gate.
    """
    sections = extract_h2_sections(body, ignore_fenced_code=True)
    placeholders: list[str] = []
    for section in PLAN_BODY_SECTIONS:
        if section == "Steps":
            continue
        section_body = sections.get(section.lower())
        if section_body is not None and section_body.strip() == "_(TODO)_":
            placeholders.append(section)
    return placeholders


def _step_ids_label(members: list[Step]) -> str:
    """``step 3`` / ``steps 1, 2`` — the shared noun and id list for a bullet."""
    noun = "step" if len(members) == 1 else "steps"
    return f"{noun} {', '.join(str(s.id) for s in members)}"


def _step_group_label(members: list[Step]) -> str:
    """``step 2 (feature)`` / ``steps 1, 3 (feature)`` — ids paired with their type.

    A group holds steps of one ``change_type``, so the type always belongs to
    every id listed before it.
    """
    return f"{_step_ids_label(members)} ({members[0].change_type.value})"


def _render_testing_strategy(steps: list[Step]) -> Optional[str]:
    """Build the per-step test-strategy block appended to ``## Testing``.

    Returns ``None`` when no step carries a ``change_type`` — the signal
    for :func:`_render_plan_body` to render Testing exactly as it would
    without per-step data. Otherwise returns a trailing block: a bolded
    lead line (plain section body, not an H3, so it adds no heading anchor
    and doesn't interact with H2 splitting) followed by one bullet per
    distinct strategy, naming its steps in ``id`` order. A classified step
    gets its type's one-line strategy from
    :data:`_TESTING_STRATEGY_BY_CHANGE_TYPE`; unclassified steps in a
    partial plan are listed explicitly as ``unclassified`` — never
    dropped, never guessed.
    """
    if not any(step.change_type is not None for step in steps):
        return None
    lines = [
        "**Per-step test strategy** (derived from each step's "
        "`change_type`):",
        "",
    ]
    # Steps of one change_type collapse into one bullet, so a plan of N feature
    # steps reads as one line instead of N identical ones.
    groups: dict[ChangeType, list[Step]] = {}
    unclassified: list[Step] = []
    for step in sorted(steps, key=lambda s: s.id):
        if step.change_type is None:
            unclassified.append(step)
        else:
            groups.setdefault(step.change_type, []).append(step)
    bullets: list[tuple[int, str]] = [
        (
            members[0].id,
            f"- {_step_group_label(members)} — "
            f"{_TESTING_STRATEGY_BY_CHANGE_TYPE[kind]}",
        )
        for kind, members in groups.items()
    ]
    if unclassified:
        bullets.append(
            (
                unclassified[0].id,
                f"- {_step_ids_label(unclassified)} — unclassified; no per-step "
                "test directive.",
            )
        )
    # Bullets run in order of each group's first step, so a reader scanning for
    # a step id finds it in roughly the plan's own order.
    lines.extend(line for _, line in sorted(bullets))
    return "\n".join(lines)


def _render_plan_body(
    title: str,
    references: Optional[list[Reference]] = None,
    references_body: Optional[str] = None,
    seed_sections: Optional[dict[str, str]] = None,
    synthesized_sections: Optional[dict[str, Optional[str]]] = None,
    supplied_guardrails: Optional[dict[str, str]] = None,
    steps: Optional[list[Step]] = None,
    preserve_source_sections: bool = False,
) -> str:
    """Build the prose body seeded after the frontmatter on a new plan.

    Each section in :data:`PLAN_BODY_SECTIONS` becomes a top-level H2.
    The ``Steps`` section gets a one-line pointer to the frontmatter
    block — that's where the machine-readable list lives, and re-listing
    steps in prose is the most common drift source. ``References``
    renders the ``references`` arg as a bulleted list when present. An
    explicit ``references_body`` takes precedence for selected roadmap
    products that pass under recorded operator descriptions. Protected source
    References accompany either research representation.

    ``synthesized_sections`` (canonical title → body markdown or ``None``,
    typically produced by :func:`propose_body_sections` against the
    original seed) is the highest-precedence body-content source. Keys
    use the canonical case from :data:`PLAN_BODY_SECTIONS` (e.g.
    ``"Overview"``, ``"Out of scope"``). The recognized optional
    ``"Input"`` key is rendered only when synthesis or seed prose provides
    content, and is placed after ``Architecture``. A value of ``None`` is
    treated as "synthesis declined to fill this section" and the renderer
    falls through to ``seed_sections``. An explicit empty string is an
    authoritative empty section, used by concept synchronization to clear
    independently generated scope prose. Entries for ``"Steps"`` and ``"References"`` are
    ignored: ``Steps`` always renders the frontmatter pointer, and
    ``References`` combines research with protected source context.

    ``supplied_guardrails`` holds original-seed bodies for the four recognized
    guardrail headings. Those bodies are authoritative: they render under
    their own conditional H2s even when distillation or synthesis omitted or
    rewrote them. Guardrails absent from the original seed remain absent.

    ``seed_sections`` (case-insensitive title → body markdown, typically
    produced by :func:`extract_h2_sections` against the original seed
    file) is the fallback when ``synthesized_sections`` has no value for
    the section. Sections without a match in either source — and
    ``References`` when no explicit body, ``references``, or seed content
    exists — fall back to ``_(TODO)_``.

    ``steps`` drives the ``## Testing`` per-change-type list: when any
    step carries a ``change_type``, :func:`_render_testing_strategy`'s
    block is APPENDED below whatever the ``synthesized`` ≻ ``seed`` ≻
    ``_(TODO)_`` ladder resolved for Testing — it never replaces seeded
    or synthesized prose. The enumeration only stands alone (in place of
    the ``_(TODO)_`` placeholder) when the ladder would have rendered the
    bare placeholder and at least one step is classified. ``None`` /
    no classified steps render Testing byte-identically to before.
    ``preserve_source_sections`` omits that generated addition for a direct
    file-backed source.
    """
    seed_sections = seed_sections or {}
    synthesized_sections = synthesized_sections or {}
    supplied_guardrails = supplied_guardrails or {}

    def _pick_synthesized(section_name: str) -> Optional[str]:
        value = synthesized_sections.get(section_name)
        if not isinstance(value, str):
            return None
        return value.strip()

    def _resolved_body(section_name: str) -> Optional[str]:
        synth_body = _pick_synthesized(section_name)
        if synth_body is not None:
            return synth_body
        seed_body = seed_sections.get(section_name.lower())
        if seed_body:
            return seed_body
        return None

    def _append_section(section_name: str, body: str) -> None:
        lines.append(f"## {section_name}")
        lines.append("")
        lines.append(body)
        lines.append("")

    lines: list[str] = [f"# {title}", ""]
    for section in PLAN_BODY_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        if section == "Steps":
            lines.append("See the `steps:` block in the frontmatter.")
        elif section == "References":
            if references_body is not None:
                lines.append(references_body)
            elif references:
                for ref in references:
                    bullet = f"- [{ref.title}]({ref.url})"
                    if ref.description:
                        bullet += f" — {ref.description}"
                    lines.append(bullet)
            elif (seed_body := seed_sections.get(section.lower())):
                lines.append(seed_body)
            else:
                lines.append("_(TODO)_")
            local_references = seed_sections.get("references")
            if (
                preserve_source_sections
                and local_references
                and not _references_present(
                    local_references, "\n".join(lines[lines.index("## References") + 1:])
                )
            ):
                lines.extend(["", local_references])
        else:
            resolved_body = _resolved_body(section)
            if section == "Testing" and not preserve_source_sections:
                # Append-below, never replace: the enumeration follows the
                # resolved prose, and only stands in for the placeholder
                # when the ladder would have shipped a bare ``_(TODO)_``.
                enumeration = _render_testing_strategy(steps or [])
                if resolved_body is not None and enumeration is not None:
                    lines.append(resolved_body)
                    lines.append("")
                    lines.append(enumeration)
                elif resolved_body is not None:
                    lines.append(resolved_body)
                elif enumeration is not None:
                    lines.append(enumeration)
                else:
                    lines.append("_(TODO)_")
            elif resolved_body is not None:
                lines.append(resolved_body)
            else:
                lines.append("_(TODO)_")
        lines.append("")
        if section == "Architecture":
            input_body = _resolved_body("Input")
            if input_body is not None:
                _append_section("Input", input_body)
            for guardrail in GUARDRAIL_BODY_SECTIONS:
                guardrail_body = supplied_guardrails.get(guardrail)
                if guardrail_body:
                    _append_section(guardrail, guardrail_body)
    return "\n".join(lines).rstrip() + "\n"


def advise_path_issues(plan: Plan, repo_root: Path) -> None:
    """Emit stderr warnings for declared paths that look broken.

    Mirrors the per-step / plan-wide checks ``launcher.preflight_step_paths``
    runs at execute time, but **advisory only** — the plan is already on
    disk by the time this is called, and the create wizard's job is to
    surface drift, not to fail-fast. Run-time pre-flight will still hard-
    block execution when a path is wrong.

    The one-level-new-subdir promotion (``parent`` missing but
    ``parent.parent`` present) matches ``launcher._creates_new_subdir``
    so a step that legitimately creates a single new directory under an
    existing one stays quiet — the noisy case is a multi-level missing
    chain, which almost always means a wrong path.
    """
    # ``check_file_existence`` returns one entry per step → list of
    # ``FileCheck``. Re-key by step id for the per-step warnings and
    # flatten for the plan-wide threshold check.
    file_checks = check_file_existence(plan, repo_root)
    promoted: list[StepFileCheck] = [
        StepFileCheck(
            step_id=sfc.step_id,
            files=[
                FileCheck(
                    path=fc.path,
                    status=(
                        FileExistence.NEW
                        if (
                            fc.status == FileExistence.MISSING_PARENT
                            and (repo_root / fc.path).parent.parent.exists()
                        )
                        else fc.status
                    ),
                    created=fc.created,
                )
                for fc in sfc.files
            ],
        )
        for sfc in file_checks
    ]

    style_hint = detect_path_style_mismatch(promoted, repo_root)
    if style_hint is not None:
        pct = round(style_hint.ratio * 100)
        examples = "\n".join(f"    - {p}" for p in style_hint.examples)
        warn(
            f"plan-wide path issue — {style_hint.missing_count} "
            f"of {style_hint.total} declared paths ({pct}%) don't resolve "
            f"under `{repo_root}`. This usually means a wrong repo root "
            f"or the wizard hallucinated paths. Examples:\n{examples}\n"
            "Fix the step `files:` entries before running the plan."
        )

    for sfc in promoted:
        missing = [
            fc for fc in sfc.files
            if fc.status == FileExistence.MISSING_PARENT and not fc.created
        ]
        if not missing:
            continue
        lines = [
            f"step {sfc.step_id} declared paths that don't "
            f"resolve under `{repo_root}`:"
        ]
        for fc in missing:
            abs_path = repo_root / fc.path
            lines.append(
                f"    - `{fc.path}` (parent `{abs_path.parent}` missing)"
            )
        lines.append(
            "    Fix the step's `files:` entries, or re-run create with "
            "--from-existing pointing at a refined description."
        )
        warn("\n".join(lines))


def append_to_manifest(
    manifest_path: Path,
    repo_root: Path,
    plan_path: Path,
) -> bool:
    """Append the plan's repo-relative path to the manifest.

    Returns True when a new entry was added, False when the path was already
    listed. Creates the manifest if missing.
    """
    try:
        rel = plan_path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise CreateError(
            f"plan path {plan_path} is not inside repo root {repo_root}"
        ) from exc
    rel_str = str(rel)

    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CreateError(f"invalid JSON in {manifest_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CreateError(f"{manifest_path} top-level must be a JSON object")
    else:
        data = {}

    plans = data.get("plans", [])
    if not isinstance(plans, list):
        raise CreateError(f'"plans" in {manifest_path} must be a list')
    if rel_str in plans:
        return False
    plans.append(rel_str)
    data["plans"] = plans
    atomic_write_text(manifest_path, json.dumps(data, indent=2) + "\n")
    return True


def remove_from_manifest(
    manifest_path: Path,
    repo_root: Path,
    plan_path: Path,
) -> bool:
    """Remove the plan's repo-relative path from the manifest if present.

    Returns True when an entry was actually removed, False when the
    manifest didn't list it (or the manifest itself is absent). Treated
    as best-effort because the on-disk state has already been mutated
    (collision archive happens first) — refusing to clean up a stale
    entry shouldn't strand the caller.
    """
    if not manifest_path.is_file():
        return False
    try:
        rel = plan_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    rel_str = str(rel)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CreateError(f"invalid JSON in {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CreateError(f"{manifest_path} top-level must be a JSON object")
    plans = data.get("plans", [])
    if not isinstance(plans, list) or rel_str not in plans:
        return False
    data["plans"] = [p for p in plans if p != rel_str]
    atomic_write_text(manifest_path, json.dumps(data, indent=2) + "\n")
    return True


def _decide_replace_collisions(
    collisions: list[Collision],
    slug: str,
    input_fn: InputFn,
    replace_on_collision: Optional[bool],
    *,
    from_existing_path: Optional[Path] = None,
) -> bool:
    """Resolve the replace-vs-abort decision when a slug collides.

    Returns ``True`` when the caller should proceed by archiving the
    existing plan(s). Raises :class:`FileExistsError` when the caller
    declined or opted out, or when any collision is an unregistered
    orphan (archiving an orphan would be misleading — there's no
    manifest entry to replace; the user should adopt it via ``register``
    or delete it). Returns ``False`` when there are no collisions — the
    no-op path.

    ``from_existing_path`` exempts the named seed file from the orphan
    refusal: ``create --from-existing <orphan>`` is the canonical way
    to convert an unstructured draft into a managed plan, and the
    source file lands in the archive as part of the standard
    replacement flow. Naming the file explicitly is the user's signal
    that they know it's there.

    Resolution order: explicit ``replace_on_collision=True`` proceeds
    silently (escape hatch); a non-``--from-existing`` orphan collision
    raises with an adopt hint; explicit ``replace_on_collision=False``
    raises without prompting; ``None`` falls through to an interactive
    ``[y/N]`` prompt with default ``False``.
    """
    if not collisions:
        return False
    # Explicit ``replace_on_collision=True`` is the "I know what I'm
    # doing, clobber it" escape hatch — honor it before any orphan
    # check so scripted callers aren't blocked. The interactive and
    # explicit-False paths get the strict orphan refusal because users
    # there are likelier to be surprised by an unmanaged file.
    if replace_on_collision is True:
        return True
    seed_resolved = (
        from_existing_path.resolve()
        if from_existing_path is not None
        else None
    )
    # Split collisions into "user-named seed" (auto-approved for
    # archival — the user told us about this file by passing it to
    # --from-existing) and "everything else" (subject to the normal
    # orphan / prompt / abort flow).
    non_seed = [
        c for c in collisions if c.path.resolve() != seed_resolved
    ]
    if not non_seed:
        # The only collision is the seed file the user pointed at. No
        # prompt, no orphan refusal — replacement is implicit in the
        # --from-existing contract, which archives the source as part
        # of the canonical conversion flow.
        return True
    orphans = [c for c in non_seed if not c.registered]
    if orphans:
        first = orphans[0]
        raise FileExistsError(
            f"a plan for slug {slug!r} already exists at {first.path} "
            f"but is not registered in the manifest. "
            f"Run `plan-tool register {first.path}` to adopt it, "
            f"or delete the file before re-running create."
        )
    if replace_on_collision is False:
        raise FileExistsError(
            f"a plan for slug {slug!r} already exists: {non_seed[0].path}"
        )
    print(f"a plan for slug {slug!r} already exists:")
    for c in non_seed:
        print(f"  {c.path}")
    if _ask_yn(
        input_fn, "Replace it (archive existing)?", default=False
    ):
        return True
    raise FileExistsError(
        f"a plan for slug {slug!r} already exists: {non_seed[0].path}"
    )


def _persist_or_clear_concepts(
    plan_path: Path, concept_tree: ConceptTree, *, safe_to_clear: bool,
) -> None:
    """Save ``concept_tree`` if non-empty. On an empty result, clear a
    pre-existing sidecar only when ``safe_to_clear`` — i.e. the merge that
    produced it was ``carry_forward_decisions`` (proven never to drop a
    saved deferral) or there was no saved record to begin with. The
    (dormant) full-tree ``rederive_concepts`` merge can still legitimately
    yield an empty result without a genuine retraction (e.g. a signed-off
    ``include`` node, or its own unreviewed-removal drop), so that path
    keeps the conservative pre-existing behavior: leave any sidecar as-is.
    """
    if concept_tree.concepts:
        save_concepts(plan_path, concept_tree)
    elif safe_to_clear:
        try:
            concepts_path(plan_path).unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            tool(
                f"failed to clear the stale concepts sidecar for "
                f"{plan_path} ({exc}); a retracted deferral may still "
                "read back as pending"
            )


def _safe_to_clear_concepts(saved_concepts: Optional[ConceptTree]) -> bool:
    """Keep a non-decision sidecar when a merge can legitimately empty it."""
    return (
        saved_concepts is None
        or saved_concepts.record_kind == RECORD_KIND_DECISION
    )


def _has_approved_concepts(concept_tree: ConceptTree) -> bool:
    """Whether publication must synchronize signed concept scope."""
    return any(node.review_state == "approved" for node in concept_tree.concepts)


def _resolve_new_plan_test_command(
    repo_root: Path,
    *,
    input_fn: InputFn,
    yes: bool,
) -> Optional[str]:
    """Return the qualified command, a concrete TTY answer, or no command."""
    qualified_command = qualify_uv_pytest_command(repo_root.resolve())
    if qualified_command is not None:
        return qualified_command

    if yes or not sys.stdin.isatty():
        print(
            "test command omitted: no preflight-qualified command and no "
            "interactive operator input.",
            file=sys.stderr,
        )
        return None

    operator_command = _ask(
        input_fn,
        "Test command (optional, blank to omit): ",
        default="",
    )
    if not operator_command or is_placeholder_intent(operator_command):
        return None
    return operator_command


def _prepare_create_plan(
    slug: str,
    *,
    repo_root: Path,
    output_dir_override: Optional[Path],
    manifest_path: Optional[Path],
    from_description: Optional[str],
    from_existing_path: Optional[Path],
    tracked_seed_location: Optional[TrackedSeedLocation],
    seed_body: Optional[str],
    input_fn: InputFn,
    claude_invoker: ClaudeInvoker,
    concept_invoker: ClaudeInvoker,
    foundational_invoker: Optional[ClaudeInvoker],
    capture_scenarios: bool,
    arm: Optional[str],
    replace_on_collision: Optional[bool],
    yes: bool,
    resume: bool,
    budget: IterativeBudget,
    synthesize_body: bool,
    offer_intents: bool,
    allow_placeholder_body: bool,
    fetch_docs: bool,
    distill: bool,
    run_logger: Optional[RunLoggerLike],
) -> CreateResult | PreparedCreatePlan:
    """Prepare a plan before publication and convergence."""
    reject_unmatched_create_sources(
        seed_body=seed_body,
        from_description=from_description,
        source=from_existing_path if from_existing_path is not None else "create seed",
    )
    validate_slug(slug)
    file_backed_intake: Optional[FileBackedSourceIntake] = None
    if from_existing_path is not None:
        file_backed_intake = validate_from_existing_seed(
            select_file_backed_source(seed_body, from_description),
            source=from_existing_path,
        )

    if yes and input_fn is input:
        # Default-accepting stand-in. Only swap in when the caller hasn't
        # provided their own ``input_fn`` — tests script answers via the
        # parameter and need their scripted values intact.
        input_fn = _silent_input_fn

    if output_dir_override is None:
        default = str(DEFAULT_OUTPUT_DIR)
        chosen = _ask(
            input_fn,
            f"Output directory (repo-relative) [{default}]: ",
            default=default,
        )
        output_dir = resolve_output_dir(repo_root, Path(chosen))
    else:
        output_dir = resolve_output_dir(repo_root, output_dir_override)

    validate_output_dir_in_repo(output_dir, repo_root)

    # A tracked source is selected by the CLI before any root relocation.
    # Read its product rows once so neither prompt construction nor later
    # publication can silently adopt a different roadmap locator.
    roadmap_research_targets = (
        _load_roadmap_research_targets(tracked_seed_location)
        if tracked_seed_location is not None
        else ()
    )
    # Validate local fallbacks before any authoring invoker can run. A local
    # row with no usable description must never spend a generic fallback call.
    local_roadmap_research_verdicts = _local_roadmap_research_verdicts(
        roadmap_research_targets
    )

    mf = manifest_path or default_manifest_path(repo_root)
    collisions = find_collisions(
        output_dir, slug, manifest_path=mf, repo_root=repo_root
    )
    should_replace = _decide_replace_collisions(
        collisions,
        slug,
        input_fn,
        replace_on_collision,
        from_existing_path=from_existing_path,
    )

    default_lessons = _default_lessons_path(repo_root, output_dir, slug)
    title, priority, lessons = prompt_metadata(
        input_fn,
        default_lessons=default_lessons,
        default_title=unslugify(slug),
    )
    if lessons is not None:
        validate_lessons_in_repo(lessons, repo_root)
    predicted_plan_path = predict_plan_path(output_dir, slug, priority)

    # Advisory spell check on the slug + title only (never the body --
    # see find_misspellings). Token-free, optional-dependency; a silent
    # no-op when pyspellchecker isn't installed. Surfaced as a note so a
    # slug typo doesn't get baked into the filename / manifest / details
    # dir unnoticed; carried on the result for the CLI to re-report.
    misspellings = find_misspellings({"slug": slug, "title": title})
    if misspellings:
        tool(
            "possible misspelling(s) in the plan slug/title "
            "(advisory -- proceeding):",
            level="note",
        )
        for ms in misspellings:
            hint = f" -> '{ms.suggestion}'" if ms.suggestion else ""
            print(f"  - {ms.field}: '{ms.word}'{hint}", file=sys.stderr)

    # Provenance frontmatter (legacy: previously written by the removed
    # `reformat` subcommand) is consumed here to (1) carry the original
    # seed file forward so the CLI can archive it alongside the
    # canonical and (2) carry the existing plan-details directory so
    # create can rename it to match the new plan's slug. Still read
    # for backward-compat with existing canonical files on disk;
    # nothing in plan-tool writes new provenance frontmatters today.
    provenance: Optional[CanonicalProvenance] = None
    if from_description is not None:
        provenance = read_canonical_provenance(from_description)

    # --- Distill first-pass --------------------------------------------------
    # Reorganize a raw / messy seed into canonical sections BEFORE the steps,
    # references, and body round-trips (and the convergence loop) consume it.
    # The pass may instead return a multi-plan split proposal, in which case we
    # short-circuit with a ``CreateResult`` that writes no plan. Every
    # preparation-needed file-backed source enters this pass even with
    # ``--no-distill``; inline input keeps that flag's compatibility behavior.
    # On the normalized outcome we rebind ``from_description`` / ``seed_body``
    # to the validated text so every downstream consumer reads one body source.
    distilled_seed_text: Optional[str] = None
    normalized_preparation_sections: Optional[dict[str, Optional[str]]] = None
    normalized_preparation_evidence_spans: Optional[
        dict[str, Optional[tuple[tuple[int, int], ...]]]
    ] = None
    uncarried_distilled_guardrails: list[str] = []
    dropped_refs: list[DroppedReference] = []
    raw_seed = seed_body if seed_body is not None else from_description
    direct_source_authority: Optional[_DirectSourceAuthority] = None
    selected_file_backed_route: Optional[FileBackedSourceRoute] = None
    selected_route_checkpoint: Optional[str] = None
    if (
        from_existing_path is not None
        and file_backed_intake is not None
        and file_backed_intake.direct_ready
    ):
        assert raw_seed is not None
        direct_seed_sections = extract_h2_sections(
            _strip_frontmatter(raw_seed), ignore_fenced_code=True
        )
        references_body = direct_seed_sections.get("references")
        if references_body is None:
            raise CreateError(
                "direct file-backed source lost its required `## References` "
                "section before publication"
            )
        direct_source_authority = _DirectSourceAuthority(
            source_text=raw_seed,
            seed_sections=direct_seed_sections,
            references_body=references_body,
        )
        selected_file_backed_route = FileBackedSourceRoute.DIRECT
        selected_route_checkpoint = _DIRECT_ASSESSMENT_CHECKPOINT_NAME
    supplied_guardrails = _extract_supplied_guardrails(raw_seed)
    # Same original-seed-only read as the guardrails above, and for the same
    # reason: ``## Outcome`` is not a canonical body section, so distillation
    # drops it. No substitute when the seed states none — the intent proposer
    # owns that path, and a stand-in would hide a plan with no stated why.
    seed_intent = _intent_from_seed_outcome(raw_seed)
    if direct_source_authority is not None:
        if run_logger is not None:
            run_logger.phase_start("assess_direct_source_split")
        assessment_t0 = time.monotonic()
        assessment_outcome = "ok"
        try:
            direct_assessment = assess_direct_source_split_from_claude(
                direct_source_authority.source_text,
                claude_invoker,
                slug=slug,
                output_dir=output_dir,
                repo_root=repo_root,
                resume=resume,
                input_fn=input_fn,
                run_logger=run_logger,
            )
            if direct_assessment.is_split:
                assessment_outcome = "split_proposed"
                assert direct_assessment.split is not None
                return CreateResult(
                    plan_path=None,
                    manifest_path=mf,
                    manifest_updated=False,
                    split_proposal=SplitProposal(entries=direct_assessment.split),
                    file_backed_route=FileBackedSourceRoute.SPLIT,
                    route_checkpoint_name=_DIRECT_ASSESSMENT_CHECKPOINT_NAME,
                )
        except CreateError as exc:
            # A returned but unusable assessment is a selected no-plan route,
            # not a transport failure and never a reason to publish direct.
            assessment_outcome = "refused"
            return CreateResult(
                plan_path=None,
                manifest_path=mf,
                manifest_updated=False,
                file_backed_route=FileBackedSourceRoute.REFUSED,
                route_checkpoint_name=_DIRECT_ASSESSMENT_CHECKPOINT_NAME,
                refusal_reason=str(exc),
            )
        except Exception:
            assessment_outcome = "error"
            raise
        finally:
            if run_logger is not None:
                run_logger.phase_end(
                    "assess_direct_source_split",
                    int((time.monotonic() - assessment_t0) * 1000),
                    assessment_outcome,
                )
    elif raw_seed is not None and (
        (
            file_backed_intake is not None
            and file_backed_intake.needs_preparation
        )
        or distill
    ):
        file_preparation_required = (
            file_backed_intake is not None
            and file_backed_intake.needs_preparation
        )
        seed_bytes = len(raw_seed.encode("utf-8"))
        already_canonical_small = (
            _canonical_seed_covers_all(
                extract_h2_sections(raw_seed, ignore_fenced_code=True)
            )
            and seed_bytes < DISTILL_SKIP_BELOW_BYTES
        )
        if already_canonical_small and not file_preparation_required:
            if run_logger is not None:
                run_logger.phase_start("propose_distilled_seed")
                run_logger.phase_end(
                    "propose_distilled_seed", 0, "skipped",
                    skip_reason="already_canonical",
                )
        else:
            if seed_bytes > DISTILL_ADVISE_ABOVE_BYTES:
                tool(
                    f"seed is {seed_bytes} bytes; large seeds often "
                    "describe multiple independent plans. Distilling now — will "
                    "propose a split if it spans separate efforts."
                )
            if run_logger is not None:
                run_logger.phase_start("propose_distilled_seed")
            distill_t0 = time.monotonic()
            distill_label = "ok"
            try:
                distilled = propose_distilled_seed_from_claude(
                    raw_seed,
                    claude_invoker,
                    slug=slug,
                    output_dir=output_dir,
                    repo_root=repo_root,
                    resume=resume,
                    input_fn=input_fn,
                    run_logger=run_logger,
                )
                if distilled.is_normalized and file_preparation_required:
                    assert distilled.sections is not None
                    assert distilled.evidence_spans is not None
                    unsupported_section = _unsupported_normalized_evidence_section(
                        distilled.sections, distilled.evidence_spans
                    )
                    if unsupported_section is not None:
                        distilled = DistillOutcome.refused(
                            _unsupported_evidence_refusal(unsupported_section)
                        )
                if distilled.is_split:
                    distill_label = "split_proposed"
                    assert distilled.split is not None
                    return CreateResult(
                        plan_path=None,
                        manifest_path=mf,
                        manifest_updated=False,
                        split_proposal=SplitProposal(entries=distilled.split),
                        file_backed_route=(
                            FileBackedSourceRoute.SPLIT
                            if file_preparation_required
                            else None
                        ),
                        route_checkpoint_name=(
                            _DISTILL_SEED_CHECKPOINT_NAME
                            if file_preparation_required
                            else None
                        ),
                    )
                if distilled.is_refused:
                    if file_preparation_required:
                        distill_label = "refused"
                        return CreateResult(
                            plan_path=None,
                            manifest_path=mf,
                            manifest_updated=False,
                            file_backed_route=FileBackedSourceRoute.REFUSED,
                            route_checkpoint_name=_DISTILL_SEED_CHECKPOINT_NAME,
                            refusal_reason=distilled.reason,
                        )
                    # ``--distill`` is an opt-in compatibility path for inline
                    # callers. File-backed preparation never reaches this arm.
                    distill_label = "skipped"
                elif distilled.is_normalized:
                    assert distilled.sections is not None
                    assert distilled.evidence_spans is not None
                    distilled_markdown = distilled.distilled
                    assert distilled_markdown is not None
                    reject_unmatched_create_fence(
                        distilled_markdown, "distilled create seed"
                    )
                    distilled_guardrails = _extract_supplied_guardrails(
                        distilled_markdown
                    )
                    _warn_dropped_guardrail_headings(
                        _find_dropped_guardrail_headings(
                            supplied_guardrails,
                            distilled_guardrails,
                        ),
                        stage="distillation",
                    )
                    uncarried_distilled_guardrails = (
                        _find_uncarried_guardrail_headings(
                            supplied_guardrails,
                            distilled_guardrails,
                        )
                    )
                    if file_preparation_required:
                        local_references = extract_h2_sections(
                            raw_seed, ignore_fenced_code=True
                        ).get("references")
                        if local_references:
                            distilled_markdown = (
                                distilled_markdown.rstrip()
                                + "\n\n## References\n\n" + local_references + "\n"
                            )
                    from_description = distilled_markdown
                    seed_body = distilled_markdown
                    distilled_seed_text = distilled_markdown
                    if file_preparation_required:
                        selected_file_backed_route = FileBackedSourceRoute.NORMALIZED
                        selected_route_checkpoint = _DISTILL_SEED_CHECKPOINT_NAME
                        normalized_preparation_sections = distilled.sections.copy()
                        if local_references:
                            normalized_preparation_sections["References"] = local_references
                        normalized_preparation_evidence_spans = dict(
                            distilled.evidence_spans
                        )
                    # Dropped-reference check: distillation reorganizes the
                    # seed and can silently drop an explicitly-required
                    # deliverable while keeping a dangling pointer to it
                    # (e.g. "the runbook in Section 7"). Surface those as an
                    # advisory so the author can restore dropped content
                    # before it propagates into steps / acceptance criteria.
                    dropped_refs = find_dropped_references(distilled_markdown)
                    if dropped_refs:
                        tool(
                            "the distilled plan references "
                            f"{len(dropped_refs)} artifact(s) that no acceptance "
                            "criterion pins down -- distillation may have dropped "
                            "the content these point at. Verify before continuing:",
                            level="warning",
                        )
                        for ref in dropped_refs:
                            # ``section`` is lowercased by extract_h2_sections;
                            # ``.capitalize()`` restores the canonical display
                            # form for all current section names ("risks" ->
                            # "Risks", "acceptance criteria" -> "Acceptance
                            # criteria").
                            print(
                                f"  - \"{ref.anchor}\" (referenced in "
                                f"## {ref.section.capitalize()}, absent from "
                                "## Acceptance criteria)",
                                file=sys.stderr,
                            )
            except Exception:
                distill_label = "error"
                raise
            finally:
                if run_logger is not None:
                    run_logger.phase_end(
                        "propose_distilled_seed",
                        int((time.monotonic() - distill_t0) * 1000),
                        distill_label,
                        dropped_references=[
                            {"anchor": r.anchor, "section": r.section}
                            for r in dropped_refs
                        ],
                    )

    # Classify only after the split exit, against the original selected seed
    # rather than the distilled replacement that downstream authoring uses.
    risk_profile_proposal = _propose_risk_profile_from_seed(
        raw_seed,
        claude_invoker,
        slug=slug,
        predicted_plan_path=predicted_plan_path,
        repo_root=repo_root,
        resume=resume,
        allow_resume=not should_replace,
        run_logger=run_logger,
    )

    # The seed prose every downstream consumer reads, resolved once now
    # that distillation has finished rebinding its two inputs:
    # ``seed_body`` (a separate original seed the caller resolved from
    # legacy provenance — ``None`` for every seed authored today, since
    # nothing has written provenance since ``reformat`` was removed in
    # BACKLOG #40) ≻ ``from_description`` (the seed's own text) ≻ no
    # source. Resolved once because re-deriving this ladder per consumer
    # is what let the body renderer and the canonical-seed synthesis gate
    # disagree: the gate judged the seed canonical and skipped synthesis
    # while the renderer held no sections, so every body section shipped
    # ``_(TODO)_``. See docs/how-to/pipeline/create-from-existing.md § The body source.
    body_source: Optional[str] = (
        seed_body if seed_body is not None else from_description
    )

    steps: list[Step] = []
    # Per-step purity rationales captured from the authoring proposal so the
    # review gate can show claude's reasoning beside each guess. Only the
    # ``from_description`` claude path populates it; canonical / interactive
    # sources leave it empty.
    step_rationales: dict[int, str] = {}
    step_source = (
        direct_source_authority.source_text
        if direct_source_authority is not None
        else from_description
    )
    if direct_source_authority is not None and file_backed_intake is not None:
        assert step_source is not None
        if file_backed_intake.strict_steps is not None:
            steps = file_backed_intake.strict_steps
        else:
            if run_logger is not None:
                run_logger.phase_start("propose_steps")
            phase_t0 = time.monotonic()
            phase_outcome = "ok"
            try:
                proposed = propose_steps_from_claude(
                    step_source,
                    claude_invoker,
                    repo_root=repo_root,
                    slug=slug,
                    output_dir=output_dir,
                    resume=resume,
                    input_fn=input_fn,
                    run_logger=run_logger,
                    rationales_out=None,
                    foundational_invoker=foundational_invoker,
                    capture_scenarios=capture_scenarios,
                    arm=arm,
                )
                if proposed:
                    steps = proposed
                else:
                    phase_outcome = "skipped"
                    print("claude didn't return parseable steps; falling back to interactive.")
            except Exception:
                phase_outcome = "error"
                raise
            finally:
                if run_logger is not None:
                    run_logger.phase_end(
                        "propose_steps",
                        int((time.monotonic() - phase_t0) * 1000),
                        phase_outcome,
                    )
    elif step_source is not None:
        canonical = extract_steps_from_canonical(step_source)
        if canonical:
            steps = canonical
        else:
            # Non-silent fallback: a source that has a ``## Steps`` H2 but
            # fails strict extraction was almost certainly an edited canonical
            # file. Tell the user before we silently hand its prose to Claude.
            if has_canonical_steps_marker(step_source):
                label = (
                    str(from_existing_path)
                    if from_existing_path is not None
                    else "input"
                )
                print(
                    f"source {label} has a '## Steps' section but doesn't "
                    "match the canonical shape; handing its prose to Claude "
                    "to extract steps.",
                    file=sys.stderr,
                )
            if run_logger is not None:
                run_logger.phase_start("propose_steps")
            phase_t0 = time.monotonic()
            phase_outcome = "ok"
            try:
                proposed = propose_steps_from_claude(
                    step_source,
                    claude_invoker,
                    repo_root=repo_root,
                    slug=slug,
                    output_dir=output_dir,
                    resume=resume,
                    input_fn=input_fn,
                    run_logger=run_logger,
                    rationales_out=step_rationales,
                    foundational_invoker=foundational_invoker,
                    capture_scenarios=capture_scenarios,
                    arm=arm,
                )
                if proposed:
                    steps = proposed
                else:
                    phase_outcome = "skipped"
                    print("claude didn't return parseable steps; falling back to interactive.")
            except Exception:
                phase_outcome = "error"
                raise
            finally:
                if run_logger is not None:
                    run_logger.phase_end(
                        "propose_steps",
                        int((time.monotonic() - phase_t0) * 1000),
                        phase_outcome,
                    )
    if not steps:
        if yes:
            # No interactive fallback under ``--yes`` — ``prompt_steps``'s
            # required step-title prompt (``_ask(..., required=True)`` at
            # line 502) spins against a no-input source. Fail fast with
            # an actionable error instead.
            raise CreateError(
                "--yes mode: no parseable steps from canonical or claude. "
                "Provide a richer --from-existing seed (with an explicit "
                "## Steps section or more detail in the prose) and retry."
            )
        steps = prompt_steps(input_fn)

    # Operator decision gate: confirm / override / split each step's proposed
    # change_type before ids and edges freeze into the written plan. Runs over
    # the finalized list regardless of source (proposal, canonical, manual).
    steps = _review_step_change_types(
        steps,
        input_fn=input_fn,
        invoker=claude_invoker,
        repo_root=repo_root,
        slug=slug,
        output_dir=output_dir,
        resume=resume,
        run_logger=run_logger,
        yes=yes,
        rationales=step_rationales,
    )

    steps = _seed_initial_step_status(steps)
    test_command = _resolve_new_plan_test_command(
        repo_root,
        input_fn=input_fn,
        yes=yes,
    )

    try:
        plan = Plan(
            title=title,
            intent=seed_intent,
            status=PlanStatus.PLANNING,
            priority=priority,
            lessons=lessons,
            # New plans opt into test enforcement by default; legacy plans
            # (no key) stay off. See Plan.enforce_step_tests.
            enforce_step_tests=True,
            test_command=test_command,
            steps=steps,
            source_seed=_resolve_source_seed(from_existing_path, repo_root),
        )
    except PydanticValidationError as exc:
        raise CreateError(
            f"failed to assemble plan (likely a depends_on error): {exc}"
        ) from exc

    # Concepts are derived before optional enrichment. The provisional body is
    # deterministic and gives create-time records a stable source state; an
    # unusable enrichment response therefore cannot erase seed concepts.
    prospective_plan_path = predicted_plan_path
    concept_source = (
        direct_source_authority.source_text
        if direct_source_authority is not None
        else seed_body or from_description or _render_plan_body(
            plan.title, steps=plan.steps
        )
    )
    concept_fingerprint = hashlib.sha256(concept_source.encode("utf-8")).hexdigest()
    concept_sections = parse_body_sections(
        concept_source, ignore_fenced_code=True
    )
    if not concept_sections:
        concept_sections = parse_body_sections(
            _render_plan_body(plan.title, steps=plan.steps),
            ignore_fenced_code=True,
        )
    _reject_empty_concept_headings(concept_sections)
    fresh_concepts = bootstrap_concepts(
        plan,
        concept_sections,
        plan_slug=slug,
        plan_fingerprint=concept_fingerprint,
    )
    _reject_repeated_concept_headings(concept_sections, fresh_concepts)
    saved_concepts: Optional[ConceptTree] = None
    if prospective_plan_path.exists():
        try:
            from plan_tool.review_persistence import compute_plan_fingerprint
            saved_concepts = load_concepts(
                prospective_plan_path,
                compute_plan_fingerprint(prospective_plan_path),
            )
        except StaleConceptTreeError as exc:
            raise CreateError(f"saved concept record conflicts with the plan: {exc}") from exc
        except InvalidConceptTreeError as exc:
            raise CreateError(f"saved concept record is invalid: {exc}") from exc
    if saved_concepts is not None:
        if saved_concepts.record_kind == RECORD_KIND_DECISION:
            # A flat decision record isn't a plan-text cache (unlike the
            # dormant full-tree shape below) — it never conflicts, so its
            # decisions simply carry forward onto the fresh bootstrap.
            concept_tree = carry_forward_decisions(saved_concepts, fresh_concepts)
        else:
            rederived = rederive_concepts(saved_concepts, fresh_concepts)
            if rederived.conflicts:
                raise CreateError("saved concept record conflicts with newly derived concepts")
            concept_tree = rederived.candidate
    else:
        # No enrichment: the deterministic bootstrap tree is the whole input
        # to the deferral-only gate. A lazy deferral only needs each section's
        # coarse bucket, not a fingerprint-gated cache of sub-concepts.
        concept_tree = fresh_concepts
    concept_tree, reviewed_steps = _review_create_concepts(
        concept_tree,
        plan.steps,
        input_fn=input_fn,
        yes=yes,
        interactive=(
            sys.stdin.isatty()
            and not yes
            and (input_fn is input or concept_invoker is not shell_concept_invoker)
        ),
    )
    plan = plan.model_copy(update={"steps": reviewed_steps})

    # Last authoring gate before the write: offer a drafted ``intent`` wherever
    # the seed's ``## Outcome`` map, the step proposal, the interactive loop, or
    # a wizard split left one missing. Placed here because step ids are final
    # (the change-type review splits and renumbers) and the plan is not yet on
    # disk, so accepted values ride the single initial write. ``body_source`` is
    # the already-resolved seed prose — no second source ladder.
    if offer_intents:
        plan = _offer_missing_intents(
            plan,
            input_fn=input_fn,
        invoker=claude_invoker,
            source_text=body_source or "",
            repo_root=repo_root,
            slug=slug,
            output_dir=output_dir,
            resume=resume,
            run_logger=run_logger,
            yes=yes,
        )

    # A selected tracked roadmap uses its fixed product snapshot rather than
    # seed prose. Local rows stay in-process; product mode validates every
    # external verdict before the plan can publish. Every other origin keeps
    # the historical generic References request unchanged.
    roadmap_research_verdicts: tuple[RoadmapResearchVerdict, ...] = ()
    references_body: Optional[str] = None
    if direct_source_authority is not None:
        references = []
        references_body = direct_source_authority.references_body
        if run_logger is not None:
            run_logger.phase_start("propose_references")
            run_logger.phase_end(
                "propose_references",
                0,
                "skipped",
                skip_reason="source_authoritative",
            )
    elif roadmap_research_targets:
        external_targets = tuple(
            target
            for target in roadmap_research_targets
            if target.research_disclosure == ResearchDisclosure.EXTERNAL
        )
        if external_targets:
            if run_logger is not None:
                run_logger.phase_start("propose_references")
            refs_t0 = time.monotonic()
            refs_outcome = "ok"
            try:
                roadmap_research_verdicts = propose_roadmap_references_from_claude(
                    roadmap_research_targets,
                    claude_invoker,
                    slug=slug,
                    output_dir=output_dir,
                    repo_root=repo_root,
                    resume=resume,
                    input_fn=input_fn,
                    run_logger=run_logger,
                )
            except Exception:
                refs_outcome = "error"
                raise
            finally:
                if run_logger is not None:
                    run_logger.phase_end(
                        "propose_references",
                        int((time.monotonic() - refs_t0) * 1000),
                        refs_outcome,
                    )
        else:
            if run_logger is not None:
                run_logger.phase_start("propose_references")
                run_logger.phase_end(
                    "propose_references", 0, "skipped", skip_reason="all_local"
                )
            roadmap_research_verdicts = local_roadmap_research_verdicts
        references, references_body = _selected_roadmap_references_for_publication(
            roadmap_research_targets,
            roadmap_research_verdicts,
        )
    else:
        if body_source is not None:
            research_description = body_source
        else:
            research_description = _build_research_context(title, steps)
        if run_logger is not None:
            run_logger.phase_start("propose_references")
        refs_t0 = time.monotonic()
        refs_outcome = "ok"
        try:
            reference_result = propose_references_from_claude(
                title,
                research_description,
                claude_invoker,
                slug=slug,
                output_dir=output_dir,
                repo_root=repo_root,
                resume=resume,
                input_fn=input_fn,
                run_logger=run_logger,
            )
            if reference_result.outcome == "unparseable":
                refs_outcome = "error"
                raise CreateError(
                    "terminal developer-document reference research remained "
                    "unparseable after its bounded repair; retry the original "
                    "`plan-tool create …` command."
                )
            references = list(reference_result.references)
            if reference_result.outcome == "empty":
                # A parseable empty result did not produce references but can
                # still publish the otherwise valid plan.
                refs_outcome = "skipped"
        except Exception:
            refs_outcome = "error"
            raise
        finally:
            if run_logger is not None:
                run_logger.phase_end(
                    "propose_references",
                    int((time.monotonic() - refs_t0) * 1000),
                    refs_outcome,
                )

    # H2 sections lifted from the seed populate the new plan's body in
    # place of ``_(TODO)_`` placeholders. No source yields an empty dict,
    # which ``_render_plan_body`` treats as "no substitutions" —
    # preserves the historical skeleton-only behavior of the interactive
    # path.
    references = references or []
    seed_sections = (
        direct_source_authority.seed_sections.copy()
        if direct_source_authority is not None
        else extract_h2_sections(body_source, ignore_fenced_code=True)
        if body_source is not None
        else {}
    )

    # Body-sections synthesis (third round-trip). Runs against the
    # richest available source so free-form seeds without canonical H2
    # names still produce a complete body. Skipped when no source is
    # available (interactive / ``--from`` -only path) and when the seed
    # is canonical (H2 extraction already covers every section). The
    # resulting dict flows side-by-side with ``seed_sections`` into
    # ``_render_plan_body``, which applies precedence (synthesized ≻
    # H2-extracted ≻ ``_(TODO)_``) inside the renderer — keeping the
    # two key-cases distinct and the contract documented on the
    # renderer's signature.
    #
    # ``synthesize_body=False`` (driven by ``--no-synthesize-body``) is
    # the operator opt-out: synthesis is skipped wholesale before source
    # selection or canonical detection, ``synthesized_sections`` stays
    # ``None`` (the documented "no synthesis attempted" signal — byte-
    # identical to omitting the renderer kwarg), and the fail-loud
    # ``_(TODO)_`` gate naturally fires on non-canonical seeds.
    #
    # Every skip carries a ``skip_reason`` so ``runs show`` reports which
    # of the four it was: ``no_synthesize_body`` (this opt-out),
    # ``no_source``, ``already_canonical``, ``all_null_response``.
    normalized_preparation_complete = (
        normalized_preparation_sections is not None
        and _normalized_sections_cover_all(normalized_preparation_sections)
    )
    # Only a complete normalized map earns the canonical body-synthesis skip.
    # An incomplete map retains its span provenance for the next evidence gate.
    synthesized_sections: Optional[dict[str, Optional[str]]] = (
        normalized_preparation_sections.copy()
        if normalized_preparation_complete
        else None
    )
    uncarried_synthesis_guardrails: list[str] = []
    if direct_source_authority is not None:
        if run_logger is not None:
            run_logger.phase_start("propose_body_sections")
            run_logger.phase_end(
                "propose_body_sections",
                0,
                "skipped",
                skip_reason="source_authoritative",
            )
    elif normalized_preparation_complete:
        if run_logger is not None:
            run_logger.phase_start("propose_body_sections")
            run_logger.phase_end(
                "propose_body_sections",
                0,
                "skipped",
                skip_reason="validated_preparation",
            )
    elif synthesize_body:
        # Decide up front whether synthesis will actually run (a source is
        # present and the seed isn't already canonical-complete). This gate
        # is resolved BEFORE the doc-fetch and the synthesis phase so the
        # fetch — which only earns its network cost when synthesis will
        # consume the result — runs as a sibling ``fetch_reference_docs``
        # phase ahead of ``propose_body_sections`` rather than nested
        # inside it. The canonical test reads ``seed_sections`` — the very
        # dict the renderer will use — so a skip is only ever taken on
        # sections the body is about to be filled from.
        #
        # The reason IS the gate: ``will_synthesize`` is derived from
        # ``body_skip_reason`` rather than computed beside it, so the runs
        # log can never disagree with what actually happened.
        body_skip_reason: Optional[str] = None
        if body_source is None:
            # Interactive / ``--from``-less path: nothing to synthesize from.
            body_skip_reason = "no_source"
        elif _canonical_seed_covers_all(seed_sections):
            body_skip_reason = "already_canonical"
        will_synthesize = body_skip_reason is None

        # Ground synthesis in fetched documentation. Failure / empty result
        # => empty block => seed-only synthesis, identical to the pre-fetch
        # behavior. Skipped entirely when synthesis won't run.
        reference_docs_block = ""
        local_code_context = ""
        local_code_anchors: tuple[str, ...] = ()
        dependency_cohesion_block = ""
        if will_synthesize:
            reference_docs_block = _fetch_reference_docs_block(
                references,
                fetch_docs=fetch_docs,
                slug=slug,
                output_dir=output_dir,
                repo_root=repo_root,
                resume=resume,
                input_fn=input_fn,
                run_logger=run_logger,
            )
            local_grounding = _render_local_code_grounding(body_source, repo_root)
            local_code_context = local_grounding.context
            local_code_anchors = local_grounding.resolved_anchors
            # committed_steps: a deferred/wont_do step's depends_on edge is
            # not a live claim this plan is making — nothing to verify.
            dependency_cohesion_block = _render_dependency_cohesion_block(
                _bridging_dependency_edges(plan.committed_steps)
            )

        if run_logger is not None:
            run_logger.phase_start("propose_body_sections")
        body_t0 = time.monotonic()
        body_outcome = "ok"
        try:
            if not will_synthesize:
                # ``body_skip_reason`` (set with the gate above) says which
                # of the two causes fired, so ``runs show`` reports the
                # absence of a synthesis attempt *and* why.
                body_outcome = "skipped"
            else:
                synthesized = propose_body_sections(
                    body_source,
                    claude_invoker,
                    reference_docs=reference_docs_block,
                    local_code_context=local_code_context,
                    local_code_anchors=local_code_anchors,
                    dependency_cohesion_block=dependency_cohesion_block,
                    slug=slug,
                    output_dir=output_dir,
                    repo_root=repo_root,
                    resume=resume,
                    input_fn=input_fn,
                    run_logger=run_logger,
                )
                synthesis_guardrails = _extract_supplied_guardrails(body_source)
                synthesized_guardrail_bodies = {
                    heading: synthesized[heading]
                    for heading in GUARDRAIL_BODY_SECTIONS
                    if isinstance(synthesized.get(heading), str)
                }
                retained_synthesis_guardrails = {
                    heading
                    for heading, body in synthesized_guardrail_bodies.items()
                    if body.strip()
                }
                _warn_dropped_guardrail_headings(
                    _find_dropped_guardrail_headings(
                        synthesis_guardrails,
                        retained_synthesis_guardrails,
                    ),
                    stage="body synthesis",
                )
                # ``_render_plan_body`` renders guardrail headings only from
                # ``supplied_guardrails`` (the raw seed) -- a heading
                # synthesis invents here is silently discarded, never
                # rendered, so this is the body-synthesis analog of the
                # distillation check above.
                uncarried_synthesis_guardrails = _find_uncarried_guardrail_headings(
                    synthesis_guardrails,
                    synthesized_guardrail_bodies,
                )
                if all(v is None for v in synthesized.values()):
                    # All-null returns and canonical-skips both produce
                    # "no body changes applied" downstream; bucket
                    # them together as ``skipped`` so ``runs diff`` can
                    # spot quality regressions either way — but keep them
                    # apart by ``skip_reason``, since a call that ran and
                    # returned nothing is a quality signal and a call that
                    # never ran is not.
                    body_outcome = "skipped"
                    body_skip_reason = "all_null_response"
                else:
                    synthesized_sections = synthesized
        except Exception:
            body_outcome = "error"
            raise
        finally:
            if run_logger is not None:
                # Omitted (not emitted as null) when nothing was skipped —
                # matches the opt-out branch below and the distill phase.
                skip_extra = (
                    {"skip_reason": body_skip_reason}
                    if body_skip_reason is not None
                    else {}
                )
                run_logger.phase_end(
                    "propose_body_sections",
                    int((time.monotonic() - body_t0) * 1000),
                    body_outcome,
                    **skip_extra,
                )
    else:
        if run_logger is not None:
            run_logger.phase_start("propose_body_sections")
            run_logger.phase_end(
                "propose_body_sections",
                0,
                "skipped",
                skip_reason="no_synthesize_body",
            )

    if normalized_preparation_sections is not None and not normalized_preparation_complete:
        # Preserve every accepted derived section and every materialized
        # evidence field. Synthesis may only offer text for an evidence gap;
        # step 4 owns refusing that gap before it can publish as support.
        if synthesized_sections is None:
            synthesized_sections = {}
        for section_name, section_body in normalized_preparation_sections.items():
            if section_name in _DERIVE_FROM_INTENT_SECTIONS or section_body is not None:
                synthesized_sections[section_name] = section_body

    concept_scope_sections = (
        {}
        if direct_source_authority is not None
        or normalized_preparation_sections is not None
        else render_scope_decisions(concept_tree)
    )
    signed_concept_review = _has_approved_concepts(concept_tree)
    if (
        signed_concept_review
        and direct_source_authority is None
        and normalized_preparation_sections is None
        and synthesized_sections is None
    ):
        synthesized_sections = {}
    if (
        signed_concept_review
        and direct_source_authority is None
        and normalized_preparation_sections is None
    ):
        # A signed empty section is authoritative too: remove independently
        # synthesized/seeded scope prose rather than letting it survive as a
        # second scope decision. ``None`` remains the ordinary synthesis
        # abstention value; the empty string is reserved here for the core.
        assert synthesized_sections is not None
        for section_name, section_body in concept_scope_sections.items():
            synthesized_sections[section_name.capitalize()] = section_body
            seed_sections.pop(section_name, None)

    # This is the final in-memory authoring boundary. The declaration reaches
    # the only initial write with the completed plan, never as a follow-up edit.
    risk_declaration = _resolve_risk_declaration(
        risk_profile_proposal,
        source_text=raw_seed,
        slug=slug,
        predicted_plan_path=prospective_plan_path,
        repo_root=repo_root,
        input_fn=input_fn,
        yes=yes,
        resume=resume,
        allow_resume=not should_replace,
        run_logger=run_logger,
    )
    plan = plan.model_copy(
        update={
            "risk_profile": risk_declaration.profile,
            "risk_profile_rationale": risk_declaration.rationale,
        }
    )

    # Fail-loud pre-write check: refuse to ship a plan whose body would
    # render as ``_(TODO)_`` in any required H2 section. The convergence
    # loop is the legitimate path for filling placeholders (its
    # ``apply_finding`` calls target exactly these sections), so the
    # gate is conditional on ``budget.enabled``. ``allow_placeholder_body``
    # is the explicit opt-out for proposal-consuming callers (the bench
    # harness) whose scoring never reads body sections. Runs BEFORE
    # collision archival / ``write_new_plan`` / ``append_to_manifest`` so
    # a rejection has zero on-disk side effects.
    candidate_body = _render_plan_body(
        plan.title,
        references=references,
        references_body=references_body,
        seed_sections=seed_sections,
        synthesized_sections=synthesized_sections,
        supplied_guardrails=supplied_guardrails,
        steps=plan.steps,
        preserve_source_sections=(
            direct_source_authority is not None
            or normalized_preparation_sections is not None
        ),
    )
    # ``allow_placeholder_body`` callers never read body sections at all (see
    # above), so an unmatched fence in ``candidate_body`` is equally inert for
    # them — validating it anyway would defeat the same documented bypass the
    # placeholder check honors right below.
    if not allow_placeholder_body:
        reject_unmatched_create_fence(candidate_body, predicted_plan_path)
    if not budget.enabled and not allow_placeholder_body:
        placeholders = _find_placeholder_body_sections(candidate_body)
        if placeholders:
            raise CreateError(
                f"plan body would ship with _(TODO)_ placeholders in: "
                f"{', '.join(placeholders)}. Provide richer "
                "--from-existing content, or pass --iterate to let the "
                "convergence loop fill the placeholders via apply_finding."
            )

    return PreparedCreatePlan(
        plan=plan,
        output_dir=output_dir,
        predicted_plan_path=prospective_plan_path,
        manifest_path=mf,
        collisions=collisions,
        should_replace=should_replace,
        provenance=provenance,
        from_existing_path=from_existing_path,
        concept_tree=concept_tree,
        saved_concepts=saved_concepts,
        references=references,
        seed_sections=seed_sections,
        synthesized_sections=synthesized_sections,
        supplied_guardrails=supplied_guardrails,
        risk_profile_proposal=risk_profile_proposal,
        continuation=_CreatePlanContinuation(
            from_description=from_description,
            input_fn=input_fn,
            distilled_seed=distilled_seed_text,
            uncarried_distilled_guardrails=uncarried_distilled_guardrails,
            uncarried_synthesis_guardrails=uncarried_synthesis_guardrails,
            dropped_references=dropped_refs,
            misspellings=misspellings,
        ),
        file_backed_intake=file_backed_intake,
        file_backed_route=selected_file_backed_route,
        route_checkpoint_name=selected_route_checkpoint,
        roadmap_research_targets=roadmap_research_targets,
        roadmap_research_verdicts=roadmap_research_verdicts,
        references_body=references_body,
        direct_source_authority=direct_source_authority,
        normalized_preparation_sections=normalized_preparation_sections,
        normalized_preparation_evidence_spans=normalized_preparation_evidence_spans,
    )


def _classify_created_artifact(
    plan_path: Path, manifest_path: Path, repo_root: Path
) -> Optional[_CreatedArtifact]:
    """Describe an on-disk target without changing its recoverable state."""
    if not plan_path.is_file():
        return None
    try:
        parse_plan(plan_path)
    except Exception:  # noqa: BLE001 - recovery must fail closed for retained bytes
        parse_valid = False
    else:
        parse_valid = True

    registered = False
    try:
        relative_path = str(plan_path.resolve().relative_to(repo_root.resolve()))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plans = manifest.get("plans", []) if isinstance(manifest, dict) else []
        registered = isinstance(plans, list) and relative_path in plans
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return _CreatedArtifact(plan_path, registered, parse_valid)


def _created_artifact_error(message: str, artifact: _CreatedArtifact) -> CreateError:
    """Attach deterministic recovery guidance to every retained target error."""
    if artifact.registered:
        guidance = (
            f" Plan {artifact.path} is already registered but finalization is incomplete; "
            "inspect and repair it in place before continuing."
        )
    elif artifact.parse_valid:
        guidance = (
            f" Plan artifact {artifact.path} is parse-valid but unregistered; preserve it, "
            "explicitly adopt it after review, or use it as --from-existing for a separate conversion."
        )
    else:
        guidance = (
            f" Plan artifact {artifact.path} is invalid and unregistered; preserve it for repair "
            "or remove it deliberately before retrying."
        )
    return CreateError(message + guidance, artifact=artifact)


def _publish_create_plan(
    slug: str,
    *,
    prepared: PreparedCreatePlan,
    repo_root: Path,
) -> _PublishedCreatePlan:
    """Publish one prepared plan and return its durable handoff state."""
    plan = prepared.plan
    output_dir = prepared.output_dir
    manifest_path = prepared.manifest_path

    replaced_archives: list[tuple[Path, Path]] = []
    replaced_skipped: list[str] = []
    replaced_manifest_entries: list[str] = []
    if prepared.should_replace:
        # Predict where the new plan will land so archive notices name it.
        predicted = prepared.predicted_plan_path
        for collision in prepared.collisions:
            collision_path = collision.path
            archive_result = archive_existing_source(collision_path, predicted, repo_root=repo_root)
            replaced_archives.extend(archive_result.archived)
            replaced_skipped.extend(archive_result.skipped)
            try:
                rel = collision_path.resolve().relative_to(repo_root.resolve())
            except ValueError:
                rel = None
            if rel is not None and remove_from_manifest(manifest_path, repo_root, collision_path):
                replaced_manifest_entries.append(str(rel))

    plan_path = prepared.predicted_plan_path
    try:
        plan_path = write_new_plan(
            output_dir,
            slug,
            plan,
            references=prepared.references,
            references_body=prepared.references_body,
            seed_sections=prepared.seed_sections,
            synthesized_sections=prepared.synthesized_sections,
            supplied_guardrails=prepared.supplied_guardrails,
            direct_source_authority=prepared.direct_source_authority,
            normalized_preparation_sections=prepared.normalized_preparation_sections,
        )
        try:
            parsed_plan = parse_plan(plan_path)
        except (ParseError, ValidationError) as exc:
            raise CreateError(f"plan was written but fails post-write reparse: {exc}") from exc

        plan_details_renamed_to: Optional[Path] = None
        plan_details_skip_reason: Optional[str] = None
        if prepared.from_existing_path is not None and prepared.provenance is not None:
            existing_details = resolve_existing_plan_details(
                prepared.from_existing_path, prepared.provenance
            )
            if existing_details is not None:
                plan_details_renamed_to, plan_details_skip_reason = rename_plan_details_to_slug(
                    existing_details, output_dir, slug
                )

        # The fingerprint is provenance/telemetry, never publication-critical.
        from plan_tool.review_persistence import compute_plan_fingerprint

        try:
            plan_fingerprint = compute_plan_fingerprint(plan_path)
        except Exception:
            plan_fingerprint = ""

        concept_tree = copy.deepcopy(prepared.concept_tree)
        signed_concept_scope = (
            prepared.direct_source_authority is None
            and prepared.normalized_preparation_sections is None
            and _has_approved_concepts(concept_tree)
        )
        if signed_concept_scope:
            source_plan_text = plan_path.read_bytes().decode("utf-8")
            sync_result = synchronize_concepts(
                plan_path,
                parsed_plan,
                None,
                concept_tree,
                source_plan_text=source_plan_text,
            )
            if not sync_result.succeeded:
                raise CreateError(f"failed to synchronize concepts: {sync_result.message}")
            try:
                parsed_plan = parse_plan(plan_path)
            except (ParseError, ValidationError) as exc:
                raise CreateError(
                    f"concept-synchronized plan fails post-write reparse: {exc}"
                ) from exc
            assert sync_result.plan_fingerprint is not None
            concept_tree.plan_fingerprint = sync_result.plan_fingerprint
        else:
            concept_tree.plan_fingerprint = plan_fingerprint
            _persist_or_clear_concepts(
                plan_path,
                concept_tree,
                safe_to_clear=_safe_to_clear_concepts(prepared.saved_concepts),
            )

        if _restore_materialized_evidence_and_sync_concepts(
            plan_path,
            prepared.normalized_preparation_sections,
            concept_tree,
            saved_concepts=prepared.saved_concepts,
        ):
            plan_fingerprint = concept_tree.plan_fingerprint

        manifest_updated = append_to_manifest(manifest_path, repo_root, plan_path)
        return _PublishedCreatePlan(
            plan_path=plan_path,
            concept_tree=concept_tree,
            plan_fingerprint=plan_fingerprint,
            signed_concept_scope=signed_concept_scope,
            manifest_updated=manifest_updated,
            plan_details_renamed_to=plan_details_renamed_to,
            plan_details_skip_reason=plan_details_skip_reason,
            replaced_archives=replaced_archives,
            replaced_skipped=replaced_skipped,
            replaced_manifest_entries=replaced_manifest_entries,
        )
    except KeyboardInterrupt:
        artifact = _classify_created_artifact(plan_path, manifest_path, repo_root)
        if artifact is not None:
            raise _CreateInterrupted(artifact) from None
        raise
    except CreateError as exc:
        if exc.artifact is not None:
            raise
        artifact = _classify_created_artifact(plan_path, manifest_path, repo_root)
        if artifact is not None:
            raise _created_artifact_error(str(exc), artifact) from exc
        raise
    except Exception as exc:
        artifact = _classify_created_artifact(plan_path, manifest_path, repo_root)
        if artifact is not None:
            raise _created_artifact_error(
                f"create failed after writing its target: {exc}", artifact
            ) from exc
        raise


def _converge_create_plan(
    convergence: _CreatePlanConvergence,
) -> Optional[str]:
    """Use ``plan_tool/parser.py:write_plan``, never ``write_new_plan``, for re-proposed steps."""
    plan_path = convergence.plan_path
    repo_root = convergence.repo_root
    slug = convergence.slug
    output_dir = convergence.output_dir
    from_description = convergence.from_description
    input_fn = convergence.input_fn
    claude_invoker = convergence.claude_invoker
    foundational_invoker = convergence.foundational_invoker
    capture_scenarios = convergence.capture_scenarios
    arm = convergence.arm
    budget = convergence.budget
    allow_drift = convergence.allow_drift
    auto_reconcile_on_drift = convergence.auto_reconcile_on_drift
    collision_sidecar = convergence.collision_sidecar
    triage = convergence.triage
    include_info = convergence.include_info
    skip_prose_reproposal = convergence.skip_prose_reproposal
    run_logger = convergence.run_logger
    plan_fingerprint = convergence.plan_fingerprint
    preserve_selected_roadmap_references = (
        convergence.preserve_selected_roadmap_references
    )
    reject_unmatched_create_fence(
        plan_path.read_text(encoding="utf-8"), plan_path
    )
    # Post-write convergence loop. The disabled default makes
    # ``should_continue`` short-circuit on its first check.
    #
    # Per iteration: re-run the deterministic completeness primitives,
    # hand any open findings to ``apply_finding`` (same code path the
    # reconcile-plan-walk's apply branch uses), then re-invoke
    # ``propose_steps_from_claude`` and, for unselected creates,
    # ``propose_references_from_claude`` with the next iteration index so the
    # checkpoint hash diverges from round 0's cached body. The new proposals
    # are written through ``write_plan`` so existing body sections survive each
    # step merge. A selected roadmap keeps its accepted References result.
    state = ConvergenceState(budget=budget)
    current_findings = collect_deterministic_findings(
        parse_plan(plan_path),
        plan_path,
        repo_root=repo_root,
        plan_name=slug,
    )
    state.current_finding_ids = frozenset(r.id for r in current_findings)

    # Iteration lock + drift-watch setup. Acquire the per-repo lock only
    # when iteration is enabled (the disabled-by-default path stays
    # lock-free). ``iteration_session`` below guarantees the lock is
    # released and the SIGINT handler restored on EVERY exit path,
    # including an unexpected exception escaping the loop body -- so a
    # crashed loop no longer leaks the lockfile and a re-run resumes from
    # the surviving checkpoints.
    _file_to_step: dict = {}
    _watched_paths: list = []
    if budget.enabled:
        # Watch only step.files for drift, NOT plan + detail (those are
        # apply_finding's legitimate edit targets every iteration).
        from plan_tool.scope_guard import (
            build_file_to_step_map,
            compute_drift_watched_paths as _cdwp,
        )
        _initial_plan = parse_plan(plan_path)
        # File->step map for drift warnings; step.files declarations stay
        # stable across the create iteration loop.
        _file_to_step = build_file_to_step_map(_initial_plan, repo_root)
        _watched_paths = _cdwp(_initial_plan, plan_path, repo_root)

    # Reuse the single best-effort fingerprint computed after publication.
    _apply_verdict_plan_fp = plan_fingerprint

    # Drift-halt sentinel. When pre- or post-apply drift fires inside the
    # for-rec loop below, set this flag and break the inner loop; the
    # outer while-loop checks it and exits.
    drift_halted = False
    parse_halted = False
    # Fingerprints (rec.id) already dispatched to apply_finding this loop.
    # A finding is applied at most once per create run: if the same
    # deterministic finding re-surfaces after an apply, repeating the same
    # guidance only spends another apply + re-scan. Keep the rec visible in
    # current_findings/state so convergence math and final open counts still
    # report it; only re-dispatch is gated.
    applied_fingerprints: set[str] = set()

    # Stage-failure sentinel. Set when an iteration's generic reference
    # research remains unparseable or its step re-proposal fails. The
    # published plan remains usable, so the CLI records an incomplete
    # iteration and exits 0; cli/authoring.py reads this result field.
    stage_failure: Optional[str] = None

    from plan_tool.drift_detection import iteration_session

    with iteration_session(
        repo_root,
        enabled=budget.enabled,
        slug=slug,
        command="create",
        loop_name="create",
        watched_paths=_watched_paths,
        file_to_step=_file_to_step,
    ) as _iter_lock:
            while True:
                cont, reason = should_continue(state)
                if not cont:
                    if budget.enabled:
                        # Visually distinct banner: the loop-stop line is the
                        # most important signal at the end of a long create run
                        # and otherwise gets buried between archive lines and
                        # stderr warnings from the iteration's claude calls.
                        bar = "─" * 60
                        open_count = len(state.current_finding_ids)
                        # Action hints depend on *why* the loop stopped.
                        # ``marginal`` / open findings → walk them or author
                        # detail files. ``deadline_exceeded`` → re-run with a
                        # bigger budget. ``max_iterations`` → re-run or audit.
                        # The slug here is the original create slug, which
                        # downstream commands accept as the plan name.
                        hints: list[str] = _open_findings_hints(
                            slug, open_count
                        )
                        if reason == "deadline_exceeded":
                            hints.append(
                                f"  plan-tool create {slug} --iteration-budget 1800   "
                                f"# resume with a larger wall-clock budget"
                            )
                        elif reason == "max_iterations":
                            hints.append(
                                f"  plan-tool create {slug} --max-iterations 5   "
                                f"# resume with a larger iteration cap"
                            )
                        elif reason == "time_budget_exceeded":
                            hints.append(
                                f"  plan-tool create {slug}   "
                                f"# time budget reached — stopped cleanly at a "
                                f"round boundary (authored steps are durable). "
                                f"Re-run to continue, or raise --time-budget."
                            )
                        hints.append(
                            f"  plan-tool status {slug}        "
                            f"# inspect plan progress"
                        )
                        hint_block = (
                            "\n  What to do:\n" + "\n".join(hints)
                            if hints else ""
                        )
                        color = color_enabled(sys.stderr)
                        bar_s = paint(bar, DIM, enabled=color)
                        headline = paint(
                            f"  iteration loop stopped: {reason}",
                            BOLD,
                            enabled=color,
                        )
                        print(
                            f"\n{bar_s}\n"
                            f"{headline}\n"
                            f"  iteration={state.iteration} · "
                            f"open_findings={open_count}"
                            f"{hint_block}\n"
                            f"{bar_s}",
                            file=sys.stderr,
                        )
                    break

                open_findings = [
                    r for r in current_findings if r.id in state.current_finding_ids
                ]
                # Impact-weighted triage (session 4 follow-up). Defer
                # findings whose complexity strictly exceeds their impact;
                # the outer iteration loop short-circuits when only deferred
                # findings remain. ``--no-triage`` opts back into legacy
                # "apply every finding" behavior.
                from plan_tool.review import (
                    emit_triage_summary,
                    partition_findings_for_triage,
                )
                open_apply, open_deferred = partition_findings_for_triage(
                    open_findings, triage_enabled=triage, include_info=include_info,
                )
                # Dedup: drop apply-eligible findings already dispatched this
                # run. ``retry_blocked`` distinguishes true convergence /
                # deferral-only from dedup exhaustion: the finding remains open,
                # but an identical re-apply will not resolve it.
                retry_blocked = [
                    r for r in open_apply if r.id in applied_fingerprints
                ]
                open_apply = [
                    r for r in open_apply if r.id not in applied_fingerprints
                ]
                emit_triage_summary(
                    open_deferred,
                    iteration_label=f"create iter {state.iteration + 1}",
                )
                if not open_apply:
                    if retry_blocked:
                        tool(
                            f"create iteration halting -- all "
                            f"{len(retry_blocked)} remaining apply-eligible "
                            f"finding(s) were already applied this run and did "
                            f"not resolve; surfaced as open for manual review."
                        )
                    elif open_deferred:
                        tool(
                            f"create iteration halting -- all "
                            f"{len(open_deferred)} remaining finding(s) are "
                            f"triaged-deferred. Apply manually or pass "
                            f"--no-triage to force-apply."
                        )
                    break
                # Sources of findings applied this round, used below to decide
                # whether the steps/references re-proposal can be skipped
                # (a prose-only round cannot change its input).
                applied_sources: set[str] = set()
                for rec in open_apply:
                    # Pre-apply drift check (task #30 -> #33). Halt before
                    # spending claude tokens on apply_finding when a watched
                    # (step.files) file was edited between applies. Mirrors
                    # cmd_completeness. ``_iter_lock`` is non-None here because
                    # ``budget.enabled`` is True (the only branch that acquires).
                    if not allow_drift and _iter_lock is not None:
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
                                    plan_slug=slug,
                                    repo_root=repo_root,
                                    run_logger=run_logger,
                                )
                            drift_halted = True
                            break

                    # Wrap each apply in an ``apply_finding_dispatch`` phase
                    # recording the finding's ``source`` + label, so a run log
                    # can bucket body-placeholder fills vs correctness/
                    # completeness applies and price each (the create loop
                    # previously left these calls unlogged). Mirrors the review
                    # walk's wrapping in review_actions.py.
                    if run_logger is not None:
                        run_logger.phase_start(
                            "apply_finding_dispatch",
                            step_id=rec.step_id,
                            source=rec.source,
                            finding_label=next(
                                (ln.strip() for ln in rec.body.splitlines()
                                 if ln.strip()),
                                rec.source,
                            ),
                        )
                    _apply_phase_t0 = time.monotonic()
                    apply_result = apply_finding(
                        plan_path,
                        repo_root=repo_root,
                        finding_body=format_recommendation_for_apply(rec),
                        step_id=rec.step_id,
                        plan_name=slug,
                        auto_fix_introduced=True,
                        run_logger=run_logger,
                        anchor=(rec.anchor or ""),
                        plan_fingerprint=_apply_verdict_plan_fp,
                    )
                    apply_reverted = revert_apply_if_parse_broken(apply_result)
                    if run_logger is not None:
                        run_logger.phase_end(
                            "apply_finding_dispatch",
                            int((time.monotonic() - _apply_phase_t0) * 1000),
                            (
                                "reverted" if apply_reverted
                                else apply_result.verdict.lower()
                            ),
                            step_id=rec.step_id,
                            source=rec.source,
                            verdict=(
                                "REVERTED" if apply_reverted
                                else apply_result.verdict
                            ),
                        )
                    if apply_reverted:
                        warn(
                            "reverted apply-finding edits: post-edit plan "
                            "failed to parse (keeping would wedge the create "
                            "iterate loop); fix the YAML and re-run"
                        )
                        parse_halted = True
                        break
                    if apply_result.verdict == "APPLIED":
                        applied_sources.add(rec.source)
                    # Mark dispatched regardless of verdict: tokens were spent,
                    # and the same rec.id should not be re-applied this run.
                    applied_fingerprints.add(rec.id)
                    # apply_finding can take 10-15 min; debounce the deadline
                    # timer so a long-but-progressing iteration doesn't trip
                    # the budget_seconds cap.
                    touch(state)

                    # Post-apply drift check. KEEP the apply's plan/detail
                    # edits (tokens already spent; edits may be useful) but
                    # halt subsequent applies. Token preservation > strict
                    # spec integrity.
                    if not allow_drift and _iter_lock is not None:
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
                            # Change-collision sidecar + pause-for-merge.
                            # When the user merges and chooses to continue,
                            # break the for-rec loop without setting
                            # ``drift_halted`` so the outer while reiterates
                            # against the merged state. On decline / headless
                            # / Ctrl-C, fall through to the legacy halt path
                            # (auto-reconcile + drift_halted=True + break).
                            if collision_sidecar:
                                from plan_tool.change_collision import (
                                    handle_drift_collision,
                                )
                                if handle_drift_collision(
                                    apply_result.pre_snapshot,
                                    repo_root=repo_root,
                                ):
                                    # Refresh the lock's content-hash
                                    # snapshot so the next iteration's
                                    # pre-apply drift check compares
                                    # against the merged state (Bug 1
                                    # from session-4 review). Without this
                                    # the immediate next pre-apply check
                                    # would halt on the same drift.
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
                                    plan_slug=slug,
                                    repo_root=repo_root,
                                    run_logger=run_logger,
                                )
                            drift_halted = True
                            break

                if drift_halted or parse_halted:
                    break

                reject_unmatched_create_fence(
                    plan_path.read_text(encoding="utf-8"), plan_path
                )

                # Post-apply short-circuit. The apply phase above may have
                # resolved the last apply-eligible finding, leaving only
                # triaged-deferred / structural findings (e.g.
                # detail-coverage, file-check) that re-authoring the step
                # graph cannot fix. Re-derive findings now and bail BEFORE
                # the re-proposal: a step re-proposal here is pure risk
                # (it's where the invalid-graph failure originated) for an
                # iteration the next ``should_continue`` would short-circuit
                # anyway. The remaining findings are resolved with
                # ``plan-tool detail`` / path fixes -- the next-steps hints
                # point there.
                #
                # Only re-derive when THIS iteration had triaged-deferred
                # findings: that's the sole case where applying the eligible
                # ones can leave a purely-deferred remainder. When nothing
                # was deferred we skip the extra deterministic pass entirely
                # (no double-compute) and let the loop re-propose + converge
                # as before -- the end-of-loop re-derive still feeds
                # ``should_continue``, so re-proposal-introduced findings are
                # still detected.
                if open_deferred:
                    post_apply_findings = collect_deterministic_findings(
                        parse_plan(plan_path),
                        plan_path,
                        repo_root=repo_root,
                        plan_name=slug,
                    )
                    post_apply, post_deferred = partition_findings_for_triage(
                        post_apply_findings,
                        triage_enabled=triage,
                        include_info=include_info,
                    )
                    post_retry_blocked = [
                        r for r in post_apply if r.id in applied_fingerprints
                    ]
                    post_apply = [
                        r for r in post_apply
                        if r.id not in applied_fingerprints
                    ]
                    if not post_apply:
                        if post_retry_blocked:
                            tool(
                                f"create iteration halting -- all "
                                f"{len(post_retry_blocked)} remaining "
                                f"apply-eligible finding(s) were already "
                                f"applied this run and did not resolve; "
                                f"surfaced as open for manual review."
                            )
                        elif post_deferred:
                            tool(
                                f"create iteration halting -- all "
                                f"{len(post_deferred)} remaining finding(s) "
                                f"are triaged-deferred. Apply manually or "
                                f"pass --no-triage to force-apply."
                            )
                        break

                next_iteration = state.iteration + 1

                # When every finding applied this round was a prose/body-section
                # edit, the steps + references re-proposal is pure
                # non-deterministic churn: propose_steps / propose_references
                # take ``edited.title + from_description`` as input (NOT the
                # edited body), and apply_finding never touches the
                # title/description -- so the re-proposal input is
                # byte-identical to round 0. Skip both claude calls and converge
                # on the deterministic re-derive that the non-skip tail also
                # runs. A/B-validated to ~halve create's Claude cost with no
                # quality regression (see experiments/minimize-claude/). On by
                # default; ``--no-skip-prose-reproposal`` opts back into the
                # always-re-propose behavior. Conservative -- skips only when
                # ALL applied sources are known prose-section fills.
                _skip_reproposal = (
                    skip_prose_reproposal
                    and _reproposal_is_skippable(applied_sources)
                )
                if _skip_reproposal:
                    tool(
                        f"create iteration {next_iteration}: skipping step + "
                        "reference re-proposal -- this round applied only prose "
                        f"findings ({sorted(applied_sources)}); the re-proposal "
                        "input (title + description) is unchanged. [Opp3]",
                        level="note",
                    )
                    if run_logger is not None:
                        run_logger.phase_end(
                            "propose_steps", 0, "skipped",
                            skip_reason="opp3_prose_only_apply",
                            iteration=next_iteration,
                        )
                    current_findings = collect_deterministic_findings(
                        parse_plan(plan_path),
                        plan_path,
                        repo_root=repo_root,
                        plan_name=slug,
                    )
                    record_iteration(state, (r.id for r in current_findings))
                    continue

                # Build the iteration input from the post-apply plan. Generic
                # reference research must finish before either proposal-side
                # writer can alter that post-apply baseline.
                edited = parse_plan(plan_path)
                edited_description = edited.title + "\n\n" + (from_description or "")
                reference_result: Optional[ReferenceResearchResult] = None
                if not preserve_selected_roadmap_references:
                    if run_logger is not None:
                        run_logger.phase_start(
                            "propose_references", iteration=next_iteration
                        )
                    refs_t0 = time.monotonic()
                    refs_outcome = "ok"
                    try:
                        reference_result = propose_references_from_claude(
                            edited.title,
                            edited_description,
                            claude_invoker,
                            slug=slug,
                            output_dir=output_dir,
                            repo_root=repo_root,
                            resume=False,
                            input_fn=input_fn,
                            run_logger=run_logger,
                            iteration=next_iteration,
                        )
                        if reference_result.outcome == "unparseable":
                            refs_outcome = "error"
                            stage_failure = (
                                "reference research failed in iteration "
                                f"{next_iteration} (terminal unparseable response)"
                            )
                        elif reference_result.outcome == "empty":
                            refs_outcome = "skipped"
                    except Exception:
                        refs_outcome = "error"
                        raise
                    finally:
                        if run_logger is not None:
                            run_logger.phase_end(
                                "propose_references",
                                int((time.monotonic() - refs_t0) * 1000),
                                refs_outcome,
                                iteration=next_iteration,
                            )

                if stage_failure is None:
                    # Re-author against the (now-edited) plan. ``resume=False`` plus
                    # the iteration-keyed input hash means each round's checkpoint
                    # lives in its own filename shard (``create-initial-steps-iter1.json``,
                    # etc.) and the cache cannot replay round 0's body.
                    notes_key_present: dict[int, bool] = {}
                    steps_proposal = propose_steps_from_claude(
                        edited_description,
                        claude_invoker,
                        repo_root=repo_root,
                        slug=slug,
                        output_dir=output_dir,
                        resume=False,
                        input_fn=input_fn,
                        run_logger=run_logger,
                        iteration=next_iteration,
                        depends_on_notes_key_present_out=notes_key_present,
                        foundational_invoker=foundational_invoker,
                        capture_scenarios=capture_scenarios,
                        arm=arm,
                    )

                    if steps_proposal:
                        # Merge each re-proposed step onto its on-disk twin, which
                        # keeps the fields the proposal must not overwrite -- see
                        # ``_preserve_on_disk_step_fields``.
                        existing_by_id = {s.id: s for s in edited.steps}
                        proposed_ids = {s.id for s in steps_proposal}

                        # Step-removal guard: if the proposal omits a step ID whose
                        # on-disk status is ``current`` or ``done``, KEEP that step
                        # intact in the merged list. Losing an in-flight or already
                        # -completed step to a regenerated proposal would silently
                        # discard execution work that ``plan-tool run`` has
                        # captured. ``pending`` steps (committed or parked) the
                        # proposal drops are allowed through — the proposal is
                        # authoritative for not-yet-started spec content.
                        preserved_dropped: list[Step] = []
                        for sid, on_disk_step in existing_by_id.items():
                            if sid in proposed_ids:
                                continue
                            if on_disk_step.status in (StepStatus.CURRENT, StepStatus.DONE):
                                tool(
                                    f"proposal dropped step {sid} "
                                    f"({on_disk_step.status.value}); keeping it in the "
                                    "merged plan -- execution work cannot be silently "
                                    "discarded by the create iteration loop.",
                                    level="warning",
                                )
                                preserved_dropped.append(on_disk_step)

                        merged_proposed = [
                            _preserve_on_disk_step_fields(
                                s,
                                existing_by_id.get(s.id),
                                proposal_included_depends_on_notes=notes_key_present.get(
                                    s.id, False
                                ),
                            )
                            for s in steps_proposal
                        ]
                        merged_steps = sorted(
                            merged_proposed + preserved_dropped, key=lambda s: s.id
                        )
                        edited = edited.model_copy(update={"steps": merged_steps})
                        # Use ``write_plan``, NOT ``write_new_plan``: ``write_plan``
                        # preserves the prose body byte-for-byte and only rewrites
                        # the frontmatter. ``write_new_plan`` would rebuild the body
                        # from the pre-loop ``seed_sections`` and clobber every
                        # section ``apply_finding`` has filled in earlier
                        # iterations.
                        # expect_unchanged=False: create owns this file across its
                        # own convergence loop (apply_finding edited it in-loop);
                        # the CAS guard is for concurrent *external* edits, not
                        # create's deliberate merge-continue write-back.
                        reject_unmatched_create_fence(
                            plan_path.read_text(encoding="utf-8"), plan_path
                        )
                        write_plan(plan_path, edited, expect_unchanged=False)
                    else:
                        # ``propose_steps_from_claude`` returned None — the
                        # re-proposal was unparseable or formed an invalid step
                        # graph (the FAILED line above carries the specifics, and
                        # the raw response is dumped under .plan-tool/parse-failures/).
                        # Fail fast: record the failure and abort the loop below
                        # rather than silently keeping the old steps and limping to a
                        # "marginal" stop. A swallowed None reads like normal
                        # convergence in the output and hides what the failed
                        # iteration did (and didn't) accomplish.
                        stage_failure = (
                            f"step re-proposal failed in iteration {next_iteration} "
                            "(unparseable output or invalid step graph)"
                        )
                        tool(
                            f"create iteration {next_iteration} "
                            "step re-proposal failed (see the FAILED line above); "
                            "keeping the round-0 steps and aborting the iteration loop.",
                            level="error",
                        )
                        if run_logger is not None:
                            run_logger.phase_end(
                                "propose_steps",
                                0,
                                "error",
                                skip_reason="reproposal_failed",
                                iteration=next_iteration,
                            )

                    # Surgical References patch — applied REGARDLESS of the steps
                    # outcome. ``write_plan`` (success branch) preserves the body
                    # byte-for-byte, so a populated reference result has nowhere to
                    # land unless patched in explicitly. Keeping this outside the
                    # steps if/else is the fix for the bug where a references round
                    # that succeeded was silently discarded just because the steps
                    # re-proposal in the same iteration failed. Only a populated
                    # result patches; an empty result preserves a directly edited or
                    # apply_finding-edited block.
                    if (
                        reference_result is not None
                        and reference_result.outcome == "populated"
                    ):
                        _patch_plan_body_section(
                            plan_path,
                            "References",
                            _render_references_body(list(reference_result.references)),
                        )

                if stage_failure is not None:
                    # Distinct FAILURE banner — deliberately NOT a
                    # ``should_continue`` stop reason. The loop is aborting
                    # because a stage broke, which must read differently from a
                    # clean converged / budget-capped stop. The published plan
                    # remains resumable, so the CLI exits 0 and records
                    # ``iteration_incomplete`` from this result field.
                    bar = "─" * 60
                    open_count = len(state.current_finding_ids)
                    # Failure-specific re-run hint + the SHARED open-findings
                    # hints (reconcile-plan-walk / detail) + status. ``detail`` is the
                    # actual fix for the structural findings the loop can't
                    # auto-resolve, so it must appear here, not just on the
                    # ``marginal`` banner.
                    failure_hints = [
                        *_open_findings_hints(
                            slug, open_count, variant="stage_failure"
                        ),
                        f"  plan-tool create {slug}        "
                        "# re-run from cached stages -- NOTE: rebuilds the body "
                        "from the seed, discarding applied edits",
                        f"  plan-tool status {slug}        "
                        "# inspect plan progress",
                    ]
                    color = color_enabled(sys.stderr)
                    bar_s = paint(bar, DIM, enabled=color)
                    headline = paint(
                        f"  iteration loop FAILED: {stage_failure}",
                        BOLD_RED,
                        enabled=color,
                    )
                    print(
                        f"\n{bar_s}\n"
                        f"{headline}\n"
                        f"  iteration={next_iteration} · open_findings={open_count}\n"
                        "  The published plan is on disk and usable. Any work "
                        "completed before\n"
                        "  the failed stage remains published; the round-0 "
                        "checkpoints were\n"
                        "  preserved so a\n"
                        "  re-run skips the cached claude stages -- but "
                        "re-running `create` rebuilds\n"
                        "  the body from the seed, discarding applied edits. "
                        "Use `completeness`\n"
                        "  below to continue in place. `create` exits 0 for "
                        "this resumable published plan;\n"
                        "  the FAILURE banner and run log keep the incomplete "
                        "iteration visible.\n"
                        "  What to do:\n"
                        + "\n".join(failure_hints) + "\n"
                        f"{bar_s}",
                        file=sys.stderr,
                    )
                    break

                current_findings = collect_deterministic_findings(
                    parse_plan(plan_path),
                    plan_path,
                    repo_root=repo_root,
                    plan_name=slug,
                )
                record_iteration(state, (r.id for r in current_findings))

    return stage_failure


_CREATE_CHECKPOINT_NAMES: tuple[str, ...] = (
    _INITIAL_STEPS_CHECKPOINT_NAME,
    _REFERENCES_CHECKPOINT_NAME,
    _BODY_SECTIONS_CHECKPOINT_NAME,
    _DISTILL_SEED_CHECKPOINT_NAME,
    _RISK_PROFILE_CHECKPOINT_NAME,
    _RISK_DECLARATION_CHECKPOINT_NAME,
    _REFERENCE_DOCS_CHECKPOINT_NAME,
    _STEP_REVIEW_CHECKPOINT_NAME,
    _INTENT_REVIEW_CHECKPOINT_NAME,
    _DIRECT_ASSESSMENT_CHECKPOINT_NAME,
)


def _apply_file_backed_checkpoint_lifecycle(
    *,
    slug: str,
    repo_root: Path,
    lifecycle: FileBackedRouteLifecycle,
    route_checkpoint_name: Optional[str],
    run_logger: Optional[RunLoggerLike],
) -> None:
    """Discard only the checkpoints selected by the route lifecycle."""
    if lifecycle.checkpoint_action == "retain":
        return
    names = (
        _CREATE_CHECKPOINT_NAMES
        if lifecycle.checkpoint_action == "discard_all"
        else ((route_checkpoint_name,) if route_checkpoint_name is not None else ())
    )
    slug_ckpt_dir = checkpoint_dir(repo_root, slug)
    if not slug_ckpt_dir.is_dir():
        return
    for name in names:
        for stale in slug_ckpt_dir.glob(f"{name}*.json"):
            try:
                removed = discard_checkpoint(stale)
            except OSError as exc:
                tool(
                    f"failed to discard checkpoint {stale} ({exc}); "
                    "next run may waste a hash-match read"
                )
                continue
            if removed and run_logger is not None:
                run_logger.checkpoint_discard(name, "success")


def _finalize_create_plan(
    slug: str,
    *,
    prepared: PreparedCreatePlan,
    published: _PublishedCreatePlan,
    iteration_stage_failure: Optional[str],
    repo_root: Path,
    budget: IterativeBudget,
    run_logger: Optional[RunLoggerLike],
) -> CreateResult:
    """Finish one published create after convergence reaches a terminal state."""
    plan_path = published.plan_path

    # Advice remains grounded in the original proposal, not convergence edits.
    advise_path_issues(prepared.plan, repo_root)
    _warn_uncarried_guardrail_headings(
        prepared.continuation.uncarried_distilled_guardrails, stage="distillation"
    )
    _warn_uncarried_guardrail_headings(
        prepared.continuation.uncarried_synthesis_guardrails, stage="body synthesis"
    )

    concept_tree = published.concept_tree
    # Convergence may rewrite plan_path while leaving its concept handoff intact.
    # Reparse only after every finalization mutator before querying coverage.
    if budget.enabled and published.signed_concept_scope:
        final_plan = parse_plan(plan_path)
        source_plan_text = plan_path.read_bytes().decode("utf-8")
        sync_result = synchronize_concepts(
            plan_path,
            final_plan,
            concept_tree,
            concept_tree,
            source_plan_text=source_plan_text,
        )
        if not sync_result.succeeded:
            raise CreateError(
                f"failed to synchronize concepts: {sync_result.message}"
            )
        final_plan = parse_plan(plan_path)
    elif budget.enabled:
        concept_tree.plan_fingerprint = published.plan_fingerprint
        _persist_or_clear_concepts(
            plan_path,
            concept_tree,
            safe_to_clear=_safe_to_clear_concepts(prepared.saved_concepts),
        )
        final_plan = parse_plan(plan_path)
    else:
        final_plan = parse_plan(plan_path)

    if _restore_materialized_evidence_and_sync_concepts(
        plan_path,
        prepared.normalized_preparation_sections,
        concept_tree,
        saved_concepts=prepared.saved_concepts,
    ):
        final_plan = parse_plan(plan_path)

    from plan_tool.completeness_report import (
        group_pending_decisions,
        pending_concept_id,
    )
    from plan_tool.review import check_concept_coverage

    pending_recs = [
        rec
        for group in group_pending_decisions(
            check_concept_coverage(
                final_plan, plan_path, plan_name=slug or ""
            )
        )
        for rec in group.recs
    ]
    if pending_recs:
        ids = ", ".join(
            cid for rec in pending_recs if (cid := pending_concept_id(rec))
        )
        tool(
            f"{len(pending_recs)} pending concept decision(s) awaiting "
            f"sign-off ({ids}) — resolve: plan-tool scope-review "
            f"{slug} --concept <id> defer|wont_do"
        )

    lifecycle = file_backed_route_lifecycle(
        prepared.file_backed_route,
        source_identity=prepared.from_existing_path,
        finalization_complete=iteration_stage_failure is None,
        normalized_payload=prepared.continuation.distilled_seed,
    )
    _apply_file_backed_checkpoint_lifecycle(
        slug=slug,
        repo_root=repo_root,
        lifecycle=lifecycle,
        route_checkpoint_name=prepared.route_checkpoint_name,
        run_logger=run_logger,
    )

    return CreateResult(
        plan_path=plan_path,
        manifest_path=prepared.manifest_path,
        manifest_updated=published.manifest_updated,
        provenance=prepared.provenance,
        plan_details_renamed_to=published.plan_details_renamed_to,
        plan_details_skip_reason=published.plan_details_skip_reason,
        replaced_archives=published.replaced_archives,
        replaced_skipped=published.replaced_skipped,
        replaced_manifest_entries=published.replaced_manifest_entries,
        distilled_seed=prepared.continuation.distilled_seed,
        dropped_references=prepared.continuation.dropped_references,
        misspellings=prepared.continuation.misspellings,
        iteration_stage_failure=iteration_stage_failure,
        file_backed_route=prepared.file_backed_route,
        route_checkpoint_name=prepared.route_checkpoint_name,
    )


def _record_selected_file_backed_route(
    result: CreateResult, run_logger: Optional[RunLoggerLike]
) -> None:
    """Record one selected file-backed terminal route when logging is active."""
    if run_logger is None or result.file_backed_route is None:
        return
    extra: dict[str, str] = {"route": result.file_backed_route.value}
    if result.file_backed_route is FileBackedSourceRoute.REFUSED:
        extra["refusal_reason"] = result.refusal_reason or "preparation refused"
    run_logger.phase_end("file_backed_route", 0, "selected", **extra)


@spawn_cwd_from_repo_root
def create_plan(
    slug: str,
    *,
    repo_root: Path,
    output_dir_override: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    from_description: Optional[str] = None,
    from_existing_path: Optional[Path] = None,
    tracked_seed_location: Optional[TrackedSeedLocation] = None,
    seed_body: Optional[str] = None,
    input_fn: InputFn = input,
    claude_invoker: ClaudeInvoker = shell_claude_invoker,
    concept_invoker: ClaudeInvoker = shell_concept_invoker,
    foundational_invoker: Optional[ClaudeInvoker] = None,
    capture_scenarios: bool = False,
    arm: Optional[str] = None,
    replace_on_collision: Optional[bool] = None,
    yes: bool = False,
    resume: bool = True,
    budget: IterativeBudget = IterativeBudget(enabled=False),
    allow_drift: bool = False,
    auto_reconcile_on_drift: bool = True,
    collision_sidecar: bool = True,
    triage: bool = True,
    include_info: bool = False,
    synthesize_body: bool = True,
    offer_intents: bool = True,
    allow_placeholder_body: bool = False,
    fetch_docs: bool = True,
    distill: bool = False,
    skip_prose_reproposal: bool = True,
    run_logger: Optional[RunLoggerLike] = None,
) -> CreateResult:
    """End-to-end wizard. Returns the created plan path and manifest status.

    ``replace_on_collision`` controls how a slug collision is handled:
    ``None`` (the default) prompts the user via ``input_fn`` with a
    default-N answer; ``True`` archives the existing plan(s) without
    prompting; ``False`` preserves the historical fail-fast behavior
    (``FileExistsError``).

    ``seed_body`` is the full markdown of a *separate* original source
    file, resolved by the caller from a canonical's provenance
    frontmatter. It is ``None`` for every seed authored today (nothing
    writes provenance since ``reformat`` was removed in BACKLOG #40), in
    which case ``from_description`` — the seed text itself — is the body
    source. Every consumer of seed prose reads that same ladder
    (``seed_body`` ≻ ``from_description``): the distill pass, the H2
    extraction that populates the new plan's body in place of
    ``_(TODO)_`` placeholders, the canonical-seed synthesis gate, the
    concept pass, and the references-research prompt.

    ``yes`` switches the wizard into a non-interactive mode that takes
    every prompt default. Concretely:

    - ``input_fn`` is replaced with a silent stand-in that returns ``""``
      so each ``_ask`` / ``_ask_yn`` / ``_ask_choice`` call resolves to
      its declared default. Custom ``input_fn`` callers (tests) are
      preserved as-is so they can still inject scripted answers.
    - If claude can't propose parseable steps from the seed, the wizard
      raises ``CreateError`` instead of falling back to the interactive
      ``prompt_steps`` loop — that loop's required-step-title prompt
      (``create.py:502``) would otherwise spin against a no-input source
      because ``_ask(..., required=True)`` re-prompts on empty input.

    When ``resume=True`` (the default) the three internal claude calls
    (initial steps + references research + body-sections synthesis) consult
    ``.plan-tool/checkpoints/<slug>/`` for cached responses keyed by slug +
    description + output dir. After the post-write ``parse_plan`` reparse
    succeeds all three checkpoints are discarded — the on-disk plan file
    is the durable artifact. ``resume=False`` skips the load (still saves
    and discards), so a ``--no-resume`` run leaves no garbage behind on
    success.

    Body synthesis (third round-trip): after the deterministic
    ``extract_h2_sections`` pass populates ``seed_sections``,
    :func:`propose_body_sections` is invoked against the richest available
    source text (``seed_body`` ≻ ``from_description`` ≻ skipped) so
    free-form seeds without canonical H2 names still produce a complete
    plan body. The synthesized dict flows side-by-side with
    ``seed_sections`` into :func:`_render_plan_body`, which applies the
    precedence (synthesized ≻ H2-extracted ≻ ``_(TODO)_``) inside the
    renderer; non-null synthesized values win, null / missing values
    fall through to ``seed_sections`` and then the placeholder. The
    call is canonical-seed-skipped via :func:`_canonical_seed_covers_all`
    — when every canonical body section already has non-empty content
    from H2 extraction, synthesis would add nothing and the round-trip
    is bypassed (logged as ``phase_end("propose_body_sections", _,
    "skipped")``). That test reads the same ``seed_sections`` the
    renderer does, which is what makes the skip safe: synthesis is
    skipped only when the renderer already holds the sections that
    justify skipping it. The fail-loud ``_(TODO)_`` gate below renders
    the candidate body with the same precedence, so both a successful
    synthesis on a free-form seed and a canonical-seed skip naturally
    satisfy the gate.

    ``synthesize_body: bool = True`` (driven by the CLI's
    ``--no-synthesize-body`` opt-out) gates that third round-trip. When
    set to ``False``, ``synthesized_sections`` stays ``None``, body
    sections fall through to H2-extraction → ``_(TODO)_``, and the
    fail-loud gate fires on non-canonical seeds — restoring pre-synthesis
    failure semantics. The opt-out is still recorded in the runs log as
    ``phase_end("propose_body_sections", _, "skipped",
    skip_reason="no_synthesize_body")``.

    Every ``propose_body_sections`` skip carries a ``skip_reason``, so
    ``runs show`` never has to guess why the round-trip did not spend a
    call: ``no_synthesize_body`` (the opt-out above), ``no_source`` (the
    interactive / ``--from``-less path), ``already_canonical`` (H2
    extraction already covers every canonical section), and
    ``all_null_response`` (the call ran and returned nothing usable —
    the only one of the four that is a quality signal rather than a
    deliberate saving).

    ``fetch_docs: bool = True`` (driven by the CLI's ``--no-fetch-docs``
    opt-out) gates reference-content fetching. When on, the URLs from the
    references round-trip are fetched, stripped to readable text, and
    folded into the body-synthesis prompt so the generated body is grounded
    in real documentation (see :func:`gather_reference_docs` /
    ``plan_tool.fetch``). The fetch is nested inside the synthesis path —
    it only runs when synthesis will actually consume the result (synthesis
    enabled, a source is present, and the seed isn't already
    canonical-complete) — and a fetch that fails or returns nothing falls
    back to seed-only synthesis. Recorded in the runs log as a
    ``fetch_reference_docs`` phase. Fetching is checkpointed under
    ``create-reference-docs.json`` keyed by the reference URL set, so a
    re-run with the same references re-uses the cached content rather than
    re-hitting the network.

    The convergence loop's CLI surface (``--iterate`` / ``--no-iterate`` /
    ``--max-iterations`` / ``--iteration-budget``) controls ``budget.enabled``;
    a disabled budget leaves the post-write loop as a no-op.

    Fail-loud TODO-body gate: when ``budget.enabled`` is False (the
    default, non-``--iterate`` path), the wizard renders the candidate
    plan body before writing and raises :class:`CreateError` if any
    required H2 section would land as ``_(TODO)_``. The check fires
    BEFORE collision archival and the manifest write, so a rejection
    leaves no on-disk side effects. ``budget.enabled=True`` bypasses
    the check because the convergence loop's ``apply_finding`` calls
    are the legitimate path for filling those placeholders.

    ``allow_placeholder_body: bool = False`` also bypasses the gate, for
    callers that consume the proposal (steps, change_types, dependency
    shape) rather than ship the body — the bench harness runs
    ``synthesize_body=False`` one-shot trials whose scoring never reads
    body sections, and without the bypass every single-plan trial dies
    at the gate regardless of backend quality. Plans written this way
    carry ``_(TODO)_`` sections by design; nothing user-facing sets it.
    """
    prepared_or_split = _prepare_create_plan(
        slug,
        repo_root=repo_root,
        output_dir_override=output_dir_override,
        manifest_path=manifest_path,
        from_description=from_description,
        from_existing_path=from_existing_path,
        tracked_seed_location=tracked_seed_location,
        seed_body=seed_body,
        input_fn=input_fn,
        claude_invoker=claude_invoker,
        concept_invoker=concept_invoker,
        foundational_invoker=foundational_invoker,
        capture_scenarios=capture_scenarios,
        arm=arm,
        replace_on_collision=replace_on_collision,
        yes=yes,
        resume=resume,
        budget=budget,
        synthesize_body=synthesize_body,
        offer_intents=offer_intents,
        allow_placeholder_body=allow_placeholder_body,
        fetch_docs=fetch_docs,
        distill=distill,
        run_logger=run_logger,
    )
    if isinstance(prepared_or_split, CreateResult):
        if prepared_or_split.file_backed_route is not None:
            lifecycle = file_backed_route_lifecycle(
                prepared_or_split.file_backed_route,
                source_identity=from_existing_path,
                finalization_complete=True,
                normalized_payload=prepared_or_split.distilled_seed,
            )
            _apply_file_backed_checkpoint_lifecycle(
                slug=slug,
                repo_root=repo_root,
                lifecycle=lifecycle,
                route_checkpoint_name=prepared_or_split.route_checkpoint_name,
                run_logger=run_logger,
            )
        _record_selected_file_backed_route(prepared_or_split, run_logger)
        return prepared_or_split

    prepared = prepared_or_split
    published = _publish_create_plan(slug, prepared=prepared, repo_root=repo_root)

    def restore_protected_evidence_after_failure() -> None:
        try:
            _restore_materialized_evidence_and_sync_concepts(
                published.plan_path,
                prepared.normalized_preparation_sections,
                published.concept_tree,
                saved_concepts=prepared.saved_concepts,
            )
        except Exception as exc:
            warn(
                f"could not restore protected evidence in retained plan "
                f"{published.plan_path}: {exc}; inspect and repair it in place"
            )

    try:
        if prepared.direct_source_authority is None:
            iteration_stage_failure = _converge_create_plan(
                _CreatePlanConvergence(
                    plan_path=published.plan_path,
                    repo_root=repo_root,
                    slug=slug,
                    output_dir=prepared.output_dir,
                    from_description=prepared.continuation.from_description,
                    input_fn=prepared.continuation.input_fn,
                    claude_invoker=claude_invoker,
                    foundational_invoker=foundational_invoker,
                    capture_scenarios=capture_scenarios,
                    arm=arm,
                    budget=budget,
                    allow_drift=allow_drift,
                    auto_reconcile_on_drift=auto_reconcile_on_drift,
                    collision_sidecar=collision_sidecar,
                    triage=triage,
                    include_info=include_info,
                    skip_prose_reproposal=skip_prose_reproposal,
                    run_logger=run_logger,
                    plan_fingerprint=published.plan_fingerprint,
                    preserve_selected_roadmap_references=bool(
                        prepared.roadmap_research_targets
                    ),
                )
            )
        else:
            iteration_stage_failure = None
        result = _finalize_create_plan(
            slug,
            prepared=prepared,
            published=published,
            iteration_stage_failure=iteration_stage_failure,
            repo_root=repo_root,
            budget=budget,
            run_logger=run_logger,
        )
        _record_selected_file_backed_route(result, run_logger)
        return result
    except KeyboardInterrupt:
        restore_protected_evidence_after_failure()
        artifact = _classify_created_artifact(
            published.plan_path, prepared.manifest_path, repo_root
        )
        if artifact is not None:
            raise _CreateInterrupted(artifact) from None
        raise
    except CreateError as exc:
        restore_protected_evidence_after_failure()
        if exc.artifact is not None:
            raise
        artifact = _classify_created_artifact(
            published.plan_path, prepared.manifest_path, repo_root
        )
        if artifact is not None:
            raise _created_artifact_error(str(exc), artifact) from exc
        raise
    except DetailFormatError:
        restore_protected_evidence_after_failure()
        raise
    except Exception as exc:
        restore_protected_evidence_after_failure()
        artifact = _classify_created_artifact(
            published.plan_path, prepared.manifest_path, repo_root
        )
        if artifact is not None:
            raise _created_artifact_error(f"create finalization failed: {exc}", artifact) from exc
        raise


# --- checkpoint helpers ---


def _relative_output_dir(output_dir: Path, repo_root: Path) -> str:
    """Render ``output_dir`` repo-relative for use in checkpoint input hashes.

    Falls back to the absolute path when ``output_dir`` resolves outside
    the repo — ``validate_output_dir_in_repo`` rejects that case at line
    402 before any propose call runs, so the fallback is dead-code defense
    for direct callers (tests) that skip the validator.
    """
    try:
        return str(output_dir.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(output_dir.resolve())


def _initial_steps_input_hash(
    slug: str,
    description: str,
    output_dir: Path,
    repo_root: Path,
    *,
    project_context: str = "",
    iteration: int = 0,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached steps proposal.

    Keyed by slug + description + output dir (repo-relative), plus confirmed
    project context when it exists. Lessons content is *not* hashed — hashing
    accumulating files defeats the resume scenario (every new lesson would
    invalidate the cache).
    Reporter and invoker callable identity are obviously not hashed;
    they're not prompt inputs.

    ``iteration`` is folded into the hash only when ``> 0`` so a
    round-0 / ``--no-iterate`` call produces a byte-identical digest to
    the pre-iteration codepath — existing on-disk checkpoints from
    earlier runs stay valid. Iteration N+1 of the post-write
    convergence loop gets its own keyspace, preventing the cache from
    short-circuiting the regeneration.
    """
    payload: dict[str, object] = {
        "slug": slug,
        "description": description,
        "output_dir": _relative_output_dir(output_dir, repo_root),
    }
    if iteration > 0:
        payload["iteration"] = iteration
    if project_context:
        payload["project_context"] = project_context
    return compute_input_hash(payload)


def _step_review_input_hash(
    slug: str,
    steps: list[Step],
    output_dir: Path,
    repo_root: Path,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached step-review result.

    Keyed on the *pre-review* proposal (slug + serialized steps + repo-relative
    output dir). A changed proposal yields a different digest so stale review
    answers are never replayed against a different step list. The serialized
    steps use ``mode="json"`` so the enum-valued fields hash by their string
    value.
    """
    payload: dict[str, object] = {
        "slug": slug,
        "steps": [s.model_dump(mode="json", exclude_none=True) for s in steps],
        "output_dir": _relative_output_dir(output_dir, repo_root),
    }
    return compute_input_hash(payload)


def _references_input_hash(
    slug: str,
    plan_title: str,
    description: str,
    output_dir: Path,
    repo_root: Path,
    *,
    iteration: int = 0,
    roadmap_targets: Optional[tuple[RoadmapResearchTarget, ...]] = None,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached references blob.

    Generic research is keyed by slug + plan_title + description + output
    dir. Selected roadmap research instead keys the immutable target snapshot,
    including each local-only field retained for step 3. The generic payload
    remains byte-identical when no snapshot is selected.

    ``iteration`` mirrors :func:`_initial_steps_input_hash` — only
    folded in when ``> 0`` so the round-0 hash stays byte-identical
    to the pre-iteration codepath.
    """
    if roadmap_targets is None:
        # Keep the legacy generic-research key byte-identical so existing
        # checkpoints remain reusable for every non-selected create origin.
        payload: dict[str, object] = {
            "slug": slug,
            "plan_title": plan_title,
            "description": description,
            "output_dir": _relative_output_dir(output_dir, repo_root),
        }
    else:
        payload = {
            "slug": slug,
            "output_dir": _relative_output_dir(output_dir, repo_root),
            "roadmap_targets": [
                {
                    "token": target.token,
                    "product": target.product,
                    "origin": target.origin,
                    "description": target.description,
                    "research_disclosure": (
                        target.research_disclosure.value
                        if target.research_disclosure is not None
                        else None
                    ),
                }
                for target in roadmap_targets
            ],
        }
    if iteration > 0:
        payload["iteration"] = iteration
    return compute_input_hash(payload)


def _reference_docs_input_hash(
    slug: str,
    urls: list[str],
    output_dir: Path,
    repo_root: Path,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached reference-docs blob.

    Keyed by slug + the ordered reference URL list + output dir
    (repo-relative). The URLs are the only fetch input that matters — the
    references' titles / descriptions don't change what content comes back
    — so a references round that returns the same URL set in the same order
    re-uses the fetched content. No ``iteration`` arg: the fetch runs once
    per create (round 0), like the distill pass.
    """
    payload: dict[str, object] = {
        "slug": slug,
        "urls": urls,
        "output_dir": _relative_output_dir(output_dir, repo_root),
    }
    return compute_input_hash(payload)


def _body_sections_input_hash(
    slug: str,
    source_text: str,
    output_dir: Path,
    repo_root: Path,
    *,
    reference_docs: str = "",
    local_code_context: str = "",
    dependency_cohesion_block: str = "",
    project_context: str = "",
    iteration: int = 0,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached synthesis response.

    Keyed by slug + source_text + output dir (repo-relative). The raw
    seed bytes (not the rendered prompt) are hashed because the prompt
    template itself can change as ``prompts/synthesize-body.md`` is
    edited; hashing the prompt would invalidate caches on every prompt
    revision, which is the wrong invalidation criterion. Seed bytes are
    what cache keys should pivot on.

    ``reference_docs``, ``local_code_context``, ``dependency_cohesion_block``,
    and confirmed ``project_context`` are synthesis inputs, so changed external
    documentation, local source evidence, the plan's bridging ``depends_on``
    edges (BACKLOG #252), or its scope boundary invalidate the cache. Each is
    folded in only when non-empty so historical no-evidence hashes stay
    byte-identical and existing checkpoints keep matching.

    ``iteration`` mirrors :func:`_initial_steps_input_hash` and
    :func:`_references_input_hash` — only folded in when ``> 0`` so the
    round-0 hash stays byte-identical to the pre-iteration codepath.
    """
    payload: dict[str, object] = {
        "slug": slug,
        "source_text": source_text,
        "output_dir": _relative_output_dir(output_dir, repo_root),
    }
    if reference_docs:
        payload["reference_docs"] = reference_docs
    if local_code_context:
        payload["local_code_context"] = local_code_context
    if dependency_cohesion_block:
        payload["dependency_cohesion_block"] = dependency_cohesion_block
    if project_context:
        payload["project_context"] = project_context
    if iteration > 0:
        payload["iteration"] = iteration
    return compute_input_hash(payload)


def _distill_seed_input_hash(
    slug: str,
    source_text: str,
    output_dir: Path,
    repo_root: Path,
    *,
    rendered_prompt: Optional[str] = None,
) -> str:
    """SHA-256 hex of the inputs that invalidate a cached distill response.

    Keyed by raw source plus the prompt and result contract that interpret the
    reply. No ``iteration`` arg: preparation runs once per create, never
    inside the convergence loop.
    """
    payload: dict[str, object] = {
        "slug": slug,
        "source_text": source_text,
        "output_dir": _relative_output_dir(output_dir, repo_root),
        "route": _PREPARATION_CACHE_DISCRIMINATOR,
        "result_contract_revision": _DISTILL_RESULT_CONTRACT_REVISION,
        "prompt_digest": hashlib.sha256(
            (rendered_prompt or _render_distill_prompt(source_text)).encode("utf-8")
        ).hexdigest(),
    }
    return compute_input_hash(payload)


def _direct_assessment_input_hash(
    slug: str,
    source_text: str,
    rendered_prompt: str,
    output_dir: Path,
    repo_root: Path,
) -> str:
    """Hash the direct decision independently from preparation output."""
    return compute_input_hash(
        {
            "slug": slug,
            "source_text": source_text,
            "output_dir": _relative_output_dir(output_dir, repo_root),
            "route": FileBackedSourceRoute.DIRECT.value,
            "result_contract_revision": _DIRECT_ASSESSMENT_CONTRACT_REVISION,
            "prompt_digest": hashlib.sha256(
                rendered_prompt.encode("utf-8")
            ).hexdigest(),
        }
    )


def _risk_profile_input_hash(
    source_text: str,
    predicted_plan_path: Path,
    rendered_prompt: str,
) -> str:
    """Hash the seed, full target, and classifier contract for safe resume."""
    return compute_input_hash(
        {
            "source_text": source_text,
            "predicted_plan_target": str(predicted_plan_path.resolve()),
            "policy_revision": _RISK_PROFILE_CLASSIFIER_POLICY_REVISION,
            "prompt_revision": hashlib.sha256(
                rendered_prompt.encode("utf-8")
            ).hexdigest(),
        }
    )


# --- small input helpers ---

def _silent_input_fn(prompt: str) -> str:
    """Non-interactive stand-in for ``input`` used under ``--yes``.

    Returns ``""`` so every ``_ask`` / ``_ask_yn`` / ``_ask_choice`` call
    resolves to its declared default. ``_ask(..., required=True)`` would
    spin against this — callers ensure they don't enter that path while
    ``--yes`` is active (see the ``prompt_steps`` guard in
    ``create_plan``).
    """
    return ""


def _checkpoint_age_minutes(c: Checkpoint) -> int:
    """Approximate age of a checkpoint in whole minutes.

    Renders the ``created_at`` ISO-8601 stamp from step 1's contract as
    "~Nm old" for the interactive resume prompt. A malformed timestamp
    (shouldn't happen — ``load_if_valid`` rejects non-strings) yields
    0, so the prompt degrades to "~0m old" rather than crashing.
    """
    try:
        created_at = datetime.fromisoformat(c.created_at)
    except ValueError:
        return 0
    delta = datetime.now(timezone.utc) - created_at
    return max(0, int(delta.total_seconds() // 60))


def _eof_default(prompt: str, value: _T) -> _T:
    """Take a prompt's documented default because stdin hit EOF.

    Non-interactive stdin without ``-y`` used to raise an unhandled
    ``EOFError`` (a crash + traceback under ``.plan-tool/crashes/``) at the
    first prompt. ``--yes`` already resolves every prompt to its default via
    ``_silent_input_fn``'s empty answer; EOF resolves the same way, warning so
    the operator sees what was decided for them. See BUG_BACKLOG.
    """
    warn(f"non-interactive stdin: taking the default for {prompt.strip()!r}")
    return value


def _ask(
    input_fn: InputFn,
    prompt: str,
    *,
    required: bool = False,
    default: Optional[str] = None,
) -> str:
    while True:
        try:
            raw = input_fn(prompt).strip()
        except EOFError:
            # A required value with no default can't be defaulted, and
            # re-prompting would spin against a closed stdin — fail clean.
            if required and default is None:
                raise CreateError(
                    f"non-interactive stdin: {prompt.strip()!r} requires a "
                    "value; re-run with -y or pass it as a flag"
                ) from None
            return _eof_default(prompt, default if default is not None else "")
        if raw:
            return raw
        if default is not None:
            return default
        if not required:
            return ""
        print("a value is required")


def _ask_choice(
    input_fn: InputFn,
    prompt: str,
    *,
    choices: tuple[str, ...],
    default: str,
) -> str:
    visible = ", ".join(c for c in choices if c)
    while True:
        try:
            raw = input_fn(f"{prompt} [{default or '<skip>'}]: ").strip().lower()
        except EOFError:
            return _eof_default(prompt, default)
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"choose one of: {visible}")


def _ask_yn(input_fn: InputFn, prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            raw = input_fn(f"{prompt} {suffix} ").strip().lower()
        except EOFError:
            return _eof_default(prompt, default)
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("please answer y or n")


def _ask_int_list(
    input_fn: InputFn,
    prompt: str,
    *,
    valid_ids: set[int],
    self_id: int,
) -> list[int]:
    """Ask for a comma-separated list of step ids, re-prompting on bad input.

    Validates against ``valid_ids`` (step ids already collected) and rejects
    ``self_id`` so we catch dependency errors at input time rather than at the
    final ``Plan(...)`` validation.
    """
    while True:
        try:
            raw = input_fn(prompt).strip()
        except EOFError:
            return _eof_default(prompt, [])
        if not raw:
            return []
        try:
            ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("please enter comma-separated integers")
            continue
        if self_id in ids:
            print(f"step {self_id} cannot depend on itself")
            continue
        unknown = [i for i in ids if i not in valid_ids]
        if unknown:
            known = sorted(valid_ids) if valid_ids else "none yet"
            print(f"unknown step id(s): {unknown} (known: {known})")
            continue
        return ids
