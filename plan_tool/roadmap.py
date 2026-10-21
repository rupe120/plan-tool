"""Roadmap orchestrator: walk the stages, gate each one, write on green.

``plan_tool.roadmap_artifacts`` owns where a roadmap's artifacts live and what
shape they have; ``plan_tool.roadmap_gates`` owns which relations they must
hold. This module is the only one of the three that shells out, and it owns
the policy applied to the other two: render a stage's prompt, make the one
Claude call, lift and parse the reply, run that stage's gates, retry with the
violations quoted back when they fail, write the artifact when they pass, and
halt the arc when a stage runs out of attempts.

**A stage is a row in a table, not a branch in the loop.** The run loop reads
``(prompt file, artifact path, parser, renderer, gate set)`` off a frozen
:class:`RoadmapStage` and never asks which stage it is running. That is what
lets a later stage arrive as a tuple entry plus a prompt file instead of a
control-flow edit — the plan's structural bet. :data:`STAGES` ships four stages:
domain, constraints, components, and plans — the fourth writes ``04-roadmap.md``
and declares the destinations for separately materialized draft seeds. A table
with no rows at all is a completed run that writes nothing.

**The first run holds stage results, then publishes once.** Each gate-clean
stage is kept in memory and copied to the resume directory
(:mod:`plan_tool.roadmap_stage_resume`); later stages' gates read the earlier
results from memory. After the last stage passes, one journaled root generation
publishes the version, a ledger-native ledger, and the accepted head (written
last). A roadmap with an accepted head is never stage-run again.

**Feedback is the reviewer's, and only a human closes it.** A revision may
propose a response on an ``open`` row, clear a prior current reopen record,
and move that row to ``awaiting-review``; removing, deferring, or ordinarily
reopening one is the human's edit, made in their editor before the next run. So
the write below
carries every feedback row the gates accepted and repairs none of them — no
state is normalized, no dropped row is put back, nothing is cleared once
answered. Clearing an answered row is the tempting one, and it deletes the
reviewer's request before they have read the response to it; nothing needs to
stop the resend, because only ``open`` rows travel as active guidance. A reply
that *authors* a review row the reviewer never wrote is refused in the attempt
loop instead (:data:`FAILURE_AUTHORED_REVIEW_ROWS`).

**Stage runs are non-interactive by construction.** No prompt, no confirm, no
TTY branch in the stage loop. The verb behaves the same unattended as under an
operator. **Apply-only promotion** (:func:`apply_roadmap_seeds`) is
separate: it reads the accepted version's roadmap artifact, never calls the invoker, and
mirrors :func:`plan_tool.scope_out.scope_out_step`'s opt-in → confirm → apply
gate when ``--apply`` is set on the CLI.

Returns facts; it never exits a process and never prints an operator summary —
the exit-code mapping and the summary belong to the CLI handler above.
"""

from __future__ import annotations

import contextlib
import dataclasses
import difflib
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from string import Template
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence

from plan_tool.fileio import atomic_write_text, is_write_temp_name
from plan_tool.model_response_sidecar import store_model_response_sidecar
from plan_tool.pathutil import latest_seed_archive
from plan_tool.renderer import prompts_dir
from plan_tool.roadmap_artifacts import (
    DecisionStatus,
    FeedbackState,
    FeedbackTargetKind,
    DRAFT_SEEDS_DIRNAME,
    LEGACY_DRAFT_SEEDS_DIRNAME,
    PLANS_FILENAME,
    PlanRow,
    PlansArtifact,
    RoadmapArtifactError,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_draft_seed_provenance,
    parse_plans_artifact,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_plans_artifact,
    resolve_draft_seed_path,
    resolve_plan_seed_dest,
    roadmap_dir,
)
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    initial_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_gates import (
    ArtifactEnvelope,
    Gate,
    Violation,
    VIOLATION_DRAFT_SEED_UNMATCHED_FENCE,
    run_components_gates,
    run_constraints_gates,
    run_domain_gates,
    run_plans_gates,
    validate_draft_seed_content,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    digest_text,
    has_invalidated_seed,
    load_seed_state,
    render_seed_state_marker,
    seed_refresh_report_path,
    seed_state_path,
    write_seed_state,
)
from plan_tool.roadmap_json import unwrap_enum_value
from plan_tool.roadmap_source import (
    CarriedDecisions,
    RoadmapSourceError,
    digest_decoded_text,
    parse_carried_decisions,
)
from plan_tool.roadmap_stage_resume import (
    RoadmapStageResumeBriefChanged,
    delete_resume,
    discard_stages_from,
    read_held_stages,
    require_matching_brief_digest,
    resume_dir_path,
    write_brief_digest,
    write_stage,
)
from plan_tool.roadmap_index import write_roadmap_index
from plan_tool.roadmap_revision_publish import (
    RoadmapPublicationRecoveryError,
    RoadmapRevisionPublishError,
    RoadmapWriterGuardError,
    RoadmapWriterToken,
    publish_roadmap_generation,
    recover_roadmap_publication,
    require_roadmap_writer_token,
    roadmap_writer_guard,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    RoadmapVersionError,
    accepted_head_path,
    build_root_enrollment_generation,
    artifact_member_name,
    load_accepted_head,
    load_accepted_version,
    prepare_root_version_from_snapshot,
    stored_artifact_path,
    version_directory_path,
    version_namespace_path,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    RoadmapSourceIdentityError,
    feedback_snapshot,
)
from plan_tool.roadmap_revision import (
    RevisionContractError,
    STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK,
    StageRevisionLimitError,
    _StageRevisionEnvelope,
    build_stage_revision_context,
    parse_stage_revision_operations,
)
from plan_tool.roadmap_revision_patch import (
    RevisionMergeError,
    StageRevisionSourceError,
    merge_stage_feedback_revision,
)
from plan_tool.project_config import StageFeedbackLimits
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_STALE,
    DraftSeedClassification,
    NoPublishedRoadmapVersionError,
    classify_draft_seeds,
    no_published_version_message,
)
from plan_tool.run_log import (
    ClaudeCallEnd,
    RunLogWriter,
    hash_prompt,
    utc_now_iso,
)
from plan_tool.scope_fence import (
    _fence_run_closes,
    _fenced_code_spans,
    _FENCE_CLOSE_RE,
    _FENCE_OPEN_RE,
    _strip_frontmatter,
    h2_section_spans,
)
from plan_tool.shell import claude_invoke


# How many times one stage may call the backend before the arc halts: one
# first pass plus two corrections. ``detail._MAX_INVOKE_ATTEMPTS`` is the
# naming precedent. Overridable per run so a test drives exhaustion cheaply.
MAX_STAGE_ATTEMPTS = 3

# The frontmatter fence a lifted reply must open on. Mirrors the private
# constant in ``roadmap_artifacts`` rather than importing it: the tolerant
# lift is this module's business and the strict parser stays the one contract.
_FRONTMATTER_FENCE = "---"

# Portable guidance shared by bounded roadmap-feedback prompts. The typed
# stage template owns the response shape and context.
REVISION_PROMPT_FILENAME = "roadmap-revision.md"
STAGE_FEEDBACK_REVISION_PROMPT_FILENAME = "roadmap-stage-feedback-revision.md"

# The local and structural single-feedback routes always judge exactly one
# update, so they share this narrower guidance instead of REVISION_PROMPT_FILENAME's
# batch-oriented "for every non-deterministic update" wording, which only
# applies where a request can also resolve as a deterministic state move.
UPDATE_JUDGMENT_PROMPT_FILENAME = "roadmap-revision-update-judgment.md"

# Every authoring stage sandwiches its own proof-scope sentence between this
# identical header and footer; only the sandwiched sentence is stage-specific.
SMALLEST_PROOF_BOUNDARY_HEADER_FILENAME = "roadmap-smallest-proof-boundary-header.md"
SMALLEST_PROOF_BOUNDARY_FOOTER_FILENAME = "roadmap-smallest-proof-boundary-footer.md"
# Shared "Writing style" body for the four authoring stages; each stage prompt
# keeps its own one-line lead sentence and includes this via ${writing_style}.
WRITING_STYLE_PROMPT_FILENAME = "roadmap-writing-style.md"

# How much of a rejected reply travels on the result as its diagnostic. Enough
# to recognize what the backend actually sent, small enough for one log line.
_REPLY_HEAD_CHARS = 400


StageInvoker = Callable[[str], "tuple[int, str]"]

# Structural typing for the run-log writer, mirroring ``create.RunLoggerLike``
# — tests pass recording fakes without the real writer's filesystem needs.
RunLoggerLike = object


def shell_roadmap_invoker(prompt: str) -> tuple[int, str]:
    """Production invoker: the active backend's ``(rc, stdout)``.

    Delegates to :func:`plan_tool.shell.claude_invoke`, so rate-limit waiting,
    backend switching, and transient backoff are inherited from
    ``plan_tool.rate_limit_loop`` below this call. The retry budget here counts
    *content* attempts only and never re-implements transport retry.
    """
    return claude_invoke(prompt)


class _MaterializationObserver:
    """Redact one seed materialization's backend lifecycle into a run log.

    Implements the same method names as :class:`RunnerObserver` /
    :class:`plan_tool.shell._ClaudeInvokeRunnerObserver`, but is not a thin
    forward like that adapter: every method here also relabels the event
    under this materializer's own phase/attempt numbering and strips
    reply-derived content, so it cannot be built by wrapping the plain
    forwarder — the two adapters share a protocol, not an implementation.
    """

    def __init__(
        self,
        run_logger: RunLoggerLike,
        *,
        plan_id: str,
        phase: str,
    ) -> None:
        self._run_logger = run_logger
        self._plan_id = plan_id
        self._phase = phase
        self._seed_attempt = 0
        self._backend_attempt = 0
        self._backend_child_started = False

    @property
    def log_path(self) -> Any:
        """The wrapped run log's path, so raw backend streams land beside it."""
        return getattr(self._run_logger, "log_path", None)

    @property
    def _current_backend_attempt(self) -> int | None:
        return self._backend_attempt or None

    def _attempt_fields(self) -> dict[str, Any]:
        return {
            "active_plan_id": self._plan_id,
            "seed_attempt": self._seed_attempt,
            "backend_attempt": self._current_backend_attempt,
            "backend_child_started": self._backend_child_started,
        }

    def _set_attempt_state(
        self,
        *,
        seed_attempt: int | None = None,
        backend_attempt: int | None = None,
        backend_child_started: bool | None = None,
    ) -> None:
        """Mutate the given attempt fields and republish context in one step.

        The sole way this observer's attempt state changes, so a future
        mutation can never land without also reaching the writer's context
        snapshot — the two were previously updated independently at each
        call site, which relied on remembering the pairing.
        """
        if seed_attempt is not None:
            self._seed_attempt = seed_attempt
        if backend_attempt is not None:
            self._backend_attempt = backend_attempt
        if backend_child_started is not None:
            self._backend_child_started = backend_child_started
        self._update_context()

    def _update_context(self) -> None:
        update_context = getattr(self._run_logger, "update_context", None)
        if update_context is None:
            return
        if not getattr(self._run_logger, "has_context", True):
            # A writer without the optional roadmap envelope still records
            # events, but has no snapshot context for attempt state.
            return
        update_context(
            seed_attempt=self._seed_attempt,
            backend_attempt=self._current_backend_attempt,
            backend_child_started=self._backend_child_started,
        )

    def _emit(self, method_name: str, **fields: Any) -> None:
        method = getattr(self._run_logger, method_name, None)
        if method is None:
            return
        method(**fields, **self._attempt_fields())

    def begin_seed_attempt(
        self, *, seed_attempt: int, prompt_bytes: int, prompt_sha256: str
    ) -> None:
        """Record the candidate before any child backend process exists."""
        self._set_attempt_state(
            seed_attempt=seed_attempt, backend_attempt=0, backend_child_started=False
        )
        self._emit(
            "claude_call_start",
            phase=self._phase,
            attempt=seed_attempt,
            prompt_bytes=prompt_bytes,
            prompt_sha256=prompt_sha256,
        )

    def candidate_failed(
        self,
        *,
        failure_kind: str,
        failure_rc: int | None,
        violation_count: int,
        reply_present: bool,
        failure_detail_present: bool,
    ) -> None:
        """Record safe materializer failure facts without reply-derived text."""
        self._emit(
            "attempt_failed",
            phase=self._phase,
            attempt=self._seed_attempt,
            failure_kind=failure_kind,
            failure_rc=failure_rc,
            violation_count=violation_count,
            reply_present=reply_present,
            failure_detail_present=failure_detail_present,
        )

    @contextlib.contextmanager
    def bind_shell_observer(self) -> Iterator[None]:
        """Bind this materializer as the active shell sink/writer for the block.

        Saves and restores the shell contextvars directly rather than going
        through ``RunLogWriter.bind_shell_sink`` — that helper installs its
        own sink/writer pair only for this override to immediately replace,
        so its installed values are never observed by anything.
        """
        if not isinstance(self._run_logger, RunLogWriter):
            yield
            return

        from plan_tool import shell

        prev_sink = shell.get_active_sink()
        prev_writer = shell.get_active_run_logger()
        shell.set_active_sink(self._claude_call_end)
        shell.set_active_run_logger(self)
        try:
            yield
        finally:
            shell.set_active_sink(prev_sink)
            shell.set_active_run_logger(prev_writer)

    def _claude_call_end(self, event: ClaudeCallEnd) -> None:
        """Write a child call end with its observed ordinal, not the seed one."""
        assert isinstance(self._run_logger, RunLogWriter)
        self._run_logger._emit(
            replace(
                event,
                run_id=self._run_logger.run_id,
                phase=self._phase,
                attempt=self._current_backend_attempt or self._seed_attempt,
            ),
            **self._attempt_fields(),
        )

    def backend_spawn(self, **fields: Any) -> None:
        self._set_attempt_state(
            backend_attempt=self._backend_attempt + 1, backend_child_started=True
        )
        self._emit(
            "backend_spawn",
            phase=self._phase,
            attempt=self._backend_attempt,
            backend=fields.get("backend", ""),
            transport=fields.get("transport"),
            child_pid=fields.get("child_pid"),
            effective_timeout_ms=fields.get("effective_timeout_ms"),
            prompt_bytes=fields.get("prompt_bytes"),
        )

    def backend_termination(self, **fields: Any) -> None:
        self._emit(
            "backend_termination",
            phase=self._phase,
            attempt=self._current_backend_attempt or self._seed_attempt,
            backend=fields.get("backend", ""),
            reason=fields.get("reason", ""),
            duration_ms=fields.get("duration_ms", 0),
            signal_or_timeout=fields.get("signal_or_timeout"),
            silent_ms=fields.get("silent_ms"),
        )

    def claude_stream_event(self, **fields: Any) -> None:
        if self._current_backend_attempt is None:
            return
        if isinstance(self._run_logger, RunLogWriter):
            self._run_logger._emit(
                _RedactedClaudeStreamEvent(
                    ts=utc_now_iso(),
                    run_id=self._run_logger.run_id,
                    phase=self._phase,
                    attempt=self._backend_attempt,
                    kind=fields.get("kind", ""),
                    tool_name=fields.get("tool_name"),
                    bytes_in_delta=fields.get("bytes_in_delta", 0),
                ),
                **self._attempt_fields(),
            )
            return
        self._emit(
            "claude_stream_event",
            phase=self._phase,
            attempt=self._backend_attempt,
            kind=fields.get("kind", ""),
            tool_name=fields.get("tool_name"),
            bytes_in_delta=fields.get("bytes_in_delta", 0),
        )

    def claude_call_progress(self, **fields: Any) -> None:
        if self._current_backend_attempt is None:
            return
        self._emit(
            "claude_call_progress",
            phase=self._phase,
            attempt=self._backend_attempt,
            elapsed_ms=fields.get("elapsed_ms", 0),
            silent_ms=fields.get("silent_ms", 0),
            last_tool=fields.get("last_tool"),
            last_activity_kind=fields.get("last_activity_kind"),
        )

    def claude_call_stall_suspected(self, **fields: Any) -> None:
        if self._current_backend_attempt is None:
            return
        self._emit(
            "claude_call_stall_suspected",
            phase=self._phase,
            attempt=self._backend_attempt,
            silent_ms=fields.get("silent_ms", 0),
            threshold_ms=fields.get("threshold_ms", 0),
            last_tool=fields.get("last_tool"),
        )

    def backend_recovery_wait(self, **fields: Any) -> None:
        if self._current_backend_attempt is None:
            return
        self._emit(
            "backend_recovery_wait",
            phase=self._phase,
            attempt=self._backend_attempt,
            reason=fields.get("reason", ""),
            delay_ms=fields.get("delay_ms", 0),
            next_attempt=self._backend_attempt + 1,
            backend=fields.get("backend", ""),
        )

    def run_interrupted(self, **fields: Any) -> None:
        if self._current_backend_attempt is None:
            return
        self._emit(
            "run_interrupted",
            phase=self._phase,
            attempt=self._backend_attempt,
            source=fields.get("source", ""),
            signal=fields.get("signal", "SIGINT"),
        )


@dataclass(frozen=True)
class _RedactedClaudeStreamEvent:
    """The stream event shape with no field that could carry tool input.

    Deliberately its own dataclass rather than a ``ClaudeStreamEvent``
    built without ``tool_input_summary``: ``asdict()`` serializes every
    dataclass field regardless of whether it was passed, so omitting the
    argument only nulls the value — the key still reaches the JSONL line.
    The redaction contract (``DATA_CONTRACT.md``) requires the key be
    absent, which only a distinct, narrower dataclass can guarantee.
    """

    ts: str
    run_id: str
    phase: str
    attempt: int
    kind: str
    tool_name: str | None
    bytes_in_delta: int
    event: str = "claude_stream_event"


# --------------------------------------------------------------------------
# The stage table
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RoadmapStage:
    """One stage of a roadmap run, expressed as data.

    Every per-stage decision the loop makes is a field here. If something feels
    like it needs an ``if`` on which stage is running, it belongs on this row
    instead — that is the whole point of the table.

    ``artifact_key`` names this stage's artifact in the two places that must
    agree: the :class:`~plan_tool.roadmap_gates.ArtifactEnvelope` keyword it
    fills, and the ``${<key>_artifact}`` prompt variable every later stage
    reads it under.
    """

    number: int
    name: str
    prompt_filename: str
    artifact_key: str
    parse: Callable[[str], Any]
    render: Callable[[Any], str]
    gates: Gate


# The shipped table, complete at four stages. A further stage appends a row
# here — an entry, never a branch.
STAGES: tuple[RoadmapStage, ...] = (
    RoadmapStage(
        number=1,
        name="domain",
        prompt_filename="roadmap-domain.md",
        artifact_key="domain",
        parse=parse_domain_artifact,
        render=render_domain_artifact,
        gates=run_domain_gates,
    ),
    RoadmapStage(
        number=2,
        name="constraints",
        prompt_filename="roadmap-constraints.md",
        artifact_key="constraints",
        parse=parse_constraints_artifact,
        render=render_constraints_artifact,
        gates=run_constraints_gates,
    ),
    RoadmapStage(
        number=3,
        name="components",
        prompt_filename="roadmap-components.md",
        artifact_key="components",
        parse=parse_components_artifact,
        render=render_components_artifact,
        gates=run_components_gates,
    ),
    RoadmapStage(
        number=4,
        name="plans",
        prompt_filename="roadmap-plans.md",
        artifact_key="plans",
        parse=parse_plans_artifact,
        render=render_plans_artifact,
        gates=run_plans_gates,
    ),
)


# --------------------------------------------------------------------------
# The result contract
# --------------------------------------------------------------------------

OUTCOME_COMPLETED = "completed"
OUTCOME_COMPLETED_NO_CHANGE = "completed-no-change"
OUTCOME_STAGE_EXHAUSTED = "stage-exhausted"
OUTCOME_STAGE_INVALID = "stage-invalid"

# The closed outcome vocabulary. Successful runs either write artifacts or
# re-gate existing artifacts without changes; exhausted and invalid stages
# return a result for the caller to report.
OUTCOMES: tuple[str, ...] = (
    OUTCOME_COMPLETED,
    OUTCOME_COMPLETED_NO_CHANGE,
    OUTCOME_STAGE_EXHAUSTED,
    OUTCOME_STAGE_INVALID,
)


def is_successful_roadmap_outcome(outcome: str) -> bool:
    """Whether a roadmap result represents a completed run."""
    return outcome in {OUTCOME_COMPLETED, OUTCOME_COMPLETED_NO_CHANGE}

# Which of the four failure kinds consumed the last attempt. One retry channel
# feeds them all, but the exhaustion *report* still has to say which one ran
# out: a backend failing rc≠0 on every attempt otherwise reports an empty
# violation list, which reads as "the model disagreed with the gates".
FAILURE_INVOKE = "invoke"
FAILURE_PARSE = "parse"
FAILURE_GATES = "gates"
# A reply that authored a review row the reviewer never wrote — see
# :func:`_authored_review_rows`. Refused in the attempt loop rather than by a gate.
FAILURE_AUTHORED_REVIEW_ROWS = "authored-review-rows"

_STATUS_FIELD_LIMIT = 80
_STATUS_BODY_LIMIT = 250
_STATUS_DIGEST_CHARS = 10

StatusCallback = Callable[[str], None]


def _bounded_status_text(value: object, *, limit: int, escaped: bool = False) -> str:
    """Escape one terminal value and retain a digest when it needs clipping."""
    text = str(value) if escaped else str(value).encode("unicode_escape").decode("ascii")
    if len(text) <= limit:
        return text
    # utf-8 with backslashreplace, not ascii: an ``escaped=True`` caller's
    # text is not guaranteed ascii-only or even valid utf-8 (e.g. a lone
    # surrogate), and backslashreplace guarantees the encode never raises.
    digest = hashlib.sha256(text.encode("utf-8", errors="backslashreplace")).hexdigest()[
        :_STATUS_DIGEST_CHARS
    ]
    suffix = f"...#{digest}"
    if limit <= len(suffix):
        return suffix[:limit]
    return f"{text[: limit - len(suffix)]}{suffix}"


def _emit_roadmap_fact(
    status_callback: StatusCallback | None,
    *,
    slug: object,
    fact: object,
    fact_is_escaped: bool = False,
) -> None:
    """Deliver one roadmap-scoped fact without affecting the stage run."""
    if status_callback is None:
        return
    try:
        slug_label = _bounded_status_text(slug, limit=_STATUS_FIELD_LIMIT)
        prefix = f"roadmap {slug_label}: "
        fact_limit = max(_STATUS_BODY_LIMIT - len(prefix), 0)
        fact_label = _bounded_status_text(fact, limit=fact_limit, escaped=fact_is_escaped)
        status_callback(f"{prefix}{fact_label}")
    except Exception:
        return


def _emit_roadmap_status(
    status_callback: StatusCallback | None,
    *,
    slug: object,
    stage: RoadmapStage,
    fact: str,
    failure_kind: str | None = None,
) -> None:
    """Deliver one bounded lifecycle fact without affecting the stage run."""
    if status_callback is None:
        return
    try:
        number_label = _bounded_status_text(stage.number, limit=_STATUS_FIELD_LIMIT)
        name_label = _bounded_status_text(stage.name, limit=_STATUS_FIELD_LIMIT)
        fact_label = _bounded_status_text(fact, limit=_STATUS_FIELD_LIMIT)
        message = f"stage {number_label} ({name_label}) {fact_label}"
        if failure_kind is not None:
            kind_label = _bounded_status_text(failure_kind, limit=_STATUS_FIELD_LIMIT)
            message += f" after {kind_label}"
    except Exception:
        return
    _emit_roadmap_fact(status_callback, slug=slug, fact=message, fact_is_escaped=True)


def _emit_accepted_stage_selection(
    status_callback: StatusCallback | None,
    *,
    slug: object,
    stages: Sequence[RoadmapStage],
) -> None:
    """Record the admitted selected rows before any of them starts."""
    if status_callback is None:
        return
    try:
        numbers = ", ".join(str(stage.number) for stage in stages)
        selection = _bounded_status_text(numbers, limit=_STATUS_FIELD_LIMIT)
        fact = f"accepted {len(stages)} stage(s) [{selection}]"
    except Exception:
        return
    _emit_roadmap_fact(status_callback, slug=slug, fact=fact, fact_is_escaped=True)


def _emit_stage_retry_status(
    status_callback: StatusCallback | None,
    *,
    slug: str,
    stage: RoadmapStage,
    attempt: int,
    failure_kind: str | None,
) -> None:
    """Report one stage retry, naming which attempt is being retried.

    A no-op on the first attempt — there is nothing to retry yet — so
    every call site can call this unconditionally instead of guarding it.
    """
    if attempt <= 1:
        return
    _emit_roadmap_status(
        status_callback,
        slug=slug,
        stage=stage,
        fact=f"retrying (attempt {attempt})",
        failure_kind=failure_kind,
    )


class _StageStopReporter:
    """Reports "stopped" for one stage attempt at most once. See :func:`_stage_run_guard`."""

    def __init__(self, status_callback: StatusCallback | None, *, slug: str, stage: RoadmapStage) -> None:
        self._status_callback = status_callback
        self._slug = slug
        self._stage = stage
        self._emitted = False

    def emit(self, *, failure_kind: str | None = None) -> None:
        if self._emitted:
            return
        self._emitted = True
        _emit_roadmap_status(
            self._status_callback,
            slug=self._slug,
            stage=self._stage,
            fact="stopped",
            failure_kind=failure_kind,
        )


@contextlib.contextmanager
def _stage_run_guard(
    status_callback: StatusCallback | None, *, slug: str, stage: RoadmapStage
) -> Iterator[_StageStopReporter]:
    """Emit "stopped" for this stage exactly once, only if the body raises.

    A break/continue/normal exit isn't an exception, so an already-resolved
    branch never reaches the except below — including one that already
    reported "stopped" itself (via the yielded reporter) before raising in
    its own follow-up bookkeeping (e.g. ``phase_end``), which is what the
    reporter's once-only ``emit()`` guards against. "stopped" after a
    positive fact ("wrote", "re-gated without write") means the run didn't
    *confirm* completion, not that nothing happened.
    """
    reporter = _StageStopReporter(status_callback, slug=slug, stage=stage)
    try:
        yield reporter
    except (RoadmapError, RoadmapArtifactError) as exc:
        reporter.emit()
        # Preserve the domain exception type while carrying the origin fact,
        # without overriding one already set (see ``_preflight_prompt_error``).
        if not hasattr(exc, "roadmap_stage_started"):
            exc.roadmap_stage_started = True
        raise
    except Exception:
        reporter.emit()
        raise


class RoadmapError(Exception):
    """A roadmap run cannot start, or cannot continue past its inputs.

    Covers the pre-flight failures: an unusable slug, a missing brief, a
    missing upstream artifact, an upstream artifact that fails its own stage's
    gates, an unreadable predecessor, a predecessor carrying a reviewer-authored
    defect no revision could fix, and a missing prompt template. A *malformed*
    upstream *or predecessor* artifact is deliberately not wrapped —
    :class:`~plan_tool.roadmap_artifacts.RoadmapArtifactError` already carries
    the path and the shape diagnosis, so it propagates as itself.
    """


class RoadmapHeadExistsError(RoadmapError):
    """A stage run was requested beside an accepted head."""


class RoadmapPreHeadStateError(RoadmapError):
    """A folder with no accepted head already holds roadmap files a stage run cannot adopt."""


class RoadmapEnvironmentalError(RoadmapError):
    """A prompt file confirmed present became unreadable — an environmental
    hiccup, not the base class's "missing template" input-shape problem, so
    ``cmd_roadmap`` maps it to rc=1 rather than the base class's rc=2.
    """


class RoadmapRunStartedWriterGuardError(RoadmapWriterGuardError):
    """A writer guard failed after the primary roadmap run started."""


def read_roadmap_text(
    path: Path,
    *,
    error_for_read_failure: Callable[[OSError | UnicodeDecodeError], Exception] | None = None,
) -> str:
    """Read UTF-8 roadmap text, leaving each route's failure meaning intact."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        if error_for_read_failure is None:
            raise
        raise error_for_read_failure(exc) from exc


@contextlib.contextmanager
def _roadmap_writer_owner(plans_dir: Path, slug: str) -> Iterator[RoadmapWriterToken]:
    """Acquire one roadmap guard after preserving the public error contract."""
    try:
        roadmap_dir(plans_dir, slug)
    except ValueError as exc:
        raise RoadmapError(str(exc)) from exc
    with roadmap_writer_guard(plans_dir, slug) as writer_token:
        yield writer_token


def refresh_roadmap_index(plans_dir: Path, slug: str) -> None:
    """Rewrite ``INDEX.md`` after a version-store change; a failed write only warns.

    Called after the publish returns, never inside the generation, so a failure cannot
    roll back or block the commit. See ``plan_tool/roadmap_index.py``.
    """
    try:
        write_roadmap_index(Path(plans_dir), slug)
    except Exception as exc:  # noqa: BLE001 - the index is a human aid and must not fail a command
        print(f"warning: roadmap {slug}: could not refresh INDEX.md ({exc})", file=sys.stderr)


def _with_initial_feedback_ledger(
    generation: PendingGeneration,
    *,
    plans_dir: Path,
    slug: str,
    ledger_state: LedgerState,
) -> PendingGeneration:
    """Add the initial ledger to a root generation, ahead of its trailing head selector."""
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    root = roadmap_dir(plans_dir, slug)
    if ledger_path.exists():
        raise RoadmapError("root enrollment requires no existing feedback ledger")
    ledger_member = GenerationMember(
        ledger_path.relative_to(root).as_posix(),
        None,
        render_ledger(initial_ledger(slug, ledger_state)),
    )
    # The generation builder orders the head selector last; keep it last so a
    # crash never leaves a head naming a version whose ledger has not landed.
    *before_head, head_member = generation.members
    return replace(generation, members=(*before_head, ledger_member, head_member))


def _require_roadmap_writer_or_raise(
    token: RoadmapWriterToken, *, plans_dir: Path, slug: str
) -> None:
    """Normalize the writer-token preflight for direct seed APIs."""
    try:
        require_roadmap_writer_token(token, plans_dir=plans_dir, slug=slug)
    except RoadmapWriterGuardError as exc:
        raise RoadmapError(str(exc)) from exc


@dataclass(frozen=True)
class RoadmapResult:
    """What one roadmap run did. Facts only — no exit code, no summary text.

    ``pending_decisions`` counts ``pending`` decision rows across the artifacts
    this run processed. It never changes ``outcome``: pending is the plan's
    review channel, and a completed run carrying twenty of them is still
    completed.

    ``artifacts`` are the published version's stored artifact paths, empty
    until the root version is published; ``written_stages`` is parallel to
    ``artifacts``. ``stages_run`` names only stages the backend authored this
    run, not stages resumed from the resume directory.

    ``feedback_awaiting_review`` counts ``awaiting-review`` feedback rows across
    the artifacts this run processed — carried rows included, since a row
    waiting through two runs waits for the same human. Like
    ``pending_decisions`` it describes the post-route artifact value. Populated on an exhausted run too — a stage can
    answer feedback and write it before a later stage spends its budget.

    ``newly_settled_decisions`` names decision ids this revision settled that
    the predecessor had not — a row it never carried, or one it carried as
    ``pending`` — artifact order, stages in run order. Advisory only:
    Status, not authorship, confers the fence, and whether an operator settled
    it is semantic, so the result delivers the ids and never flips ``outcome``.
    Empty on a first run (no predecessor).
    """

    outcome: str
    artifacts: tuple[Path, ...]
    stages_run: tuple[int, ...]
    pending_decisions: int
    feedback_awaiting_review: int = 0
    newly_settled_decisions: tuple[str, ...] = ()
    written_stages: tuple[int, ...] = ()
    failed_stage: Optional[int] = None
    violations: tuple[Violation, ...] = ()
    failure_kind: Optional[str] = None
    # Set for the invoke kind only (the rc the backend exited with), and
    # ``None`` for every other kind — a caller branches on presence.
    failure_rc: Optional[int] = None
    # The head of the reply that could not be used, for every kind whose defect
    # is the reply itself. ``None`` — not an empty string — when the run really
    # did fail on gates, so "the model disagreed" and "the backend never
    # answered" stay distinguishable.
    failure_detail: Optional[str] = None
    # A roadmap write that changes the plans artifact may invalidate derived
    # seeds without replacing them; callers direct regeneration explicitly.
    invalidated_seed_count: int = 0


def emit_roadmap_terminal_status(
    status_callback: StatusCallback | None,
    *,
    slug: object,
    result: RoadmapResult | None = None,
    disposition: str | None = None,
) -> None:
    """Deliver one closed outcome or terminal disposition through the status seam."""
    fact = disposition if disposition is not None else result.outcome if result is not None else None
    if fact is None:
        return
    if disposition is None and fact not in OUTCOMES:
        # Fail-open like every sibling emitter: the run already completed,
        # so raising here would crash a finished result over a status line.
        return
    _emit_roadmap_fact(status_callback, slug=slug, fact=fact)


# --------------------------------------------------------------------------
# Prompt assembly
# --------------------------------------------------------------------------

# Appended to an artifact-authoring stage prompt after the first. Bare bullets
# under a short header: the gates already write every message to survive this
# trip, so they are quoted verbatim and nothing is added.
#
# Corrections **replace**, they never accumulate — each attempt's block carries
# only what that attempt produced. An accumulated block re-asserts violations
# the artifact no longer has, and correcting an already-fixed violation is how
# a model reintroduces it. The bounded budget and the exhaustion report, not a
# growing list, are the mitigation for an oscillating stage.
_CORRECTIONS_HEADER = (
    "\n\n---\n\n**The previous response was rejected.** Fix exactly these and "
    "re-emit the whole artifact, with no commentary about this notice:\n\n"
)

_STAGE_FEEDBACK_CORRECTIONS_HEADER = (
    "\n\n---\n\n**The previous JSON response was rejected.** Fix exactly these "
    "and return one unfenced JSON object that matches the closed response schema, "
    "with no commentary:\n\n"
)

_CARRIED_DECISIONS_SECTION = re.compile(
    r"^## Carried decisions[ \t]*\n.*?(?=^#{1,2}[ \t]+|\Z)", re.MULTILINE | re.DOTALL
)


def _corrections_block(messages: Sequence[str]) -> str:
    return _CORRECTIONS_HEADER + "".join(f"- {message}\n" for message in messages)


def _stage_feedback_corrections_block(messages: Sequence[str]) -> str:
    return _STAGE_FEEDBACK_CORRECTIONS_HEADER + "".join(f"- {message}\n" for message in messages)


def _preflight_prompt_error(message: str) -> RoadmapError:
    """A broken prompt resource, marked not-started so ``_stage_run_guard``
    (which only fills the fact in when absent) doesn't overwrite it."""
    exc = RoadmapError(message)
    exc.roadmap_stage_started = False
    return exc


def _render_stage_prompt(
    stage: RoadmapStage,
    *,
    slug: str,
    brief: str,
    upstream: Sequence["_LoadedArtifact"],
    carried_decisions: CarriedDecisions | None = None,
) -> str:
    """Render ``stage``'s prompt from its template plus the run's inputs.

    Every stage gets the same variable map — the slug, the brief, and the text
    of every artifact *below* this stage, taken from the run's held results.

    This renderer is only for first-run authoring; a resumed held stage is
    re-gated without a model call.
    """
    template_path = prompts_dir() / stage.prompt_filename
    if not template_path.is_file():
        raise _preflight_prompt_error(
            f"no prompt template for roadmap stage {stage.number} ({stage.name}) at {template_path}"
        )
    header_path = prompts_dir() / SMALLEST_PROOF_BOUNDARY_HEADER_FILENAME
    footer_path = prompts_dir() / SMALLEST_PROOF_BOUNDARY_FOOTER_FILENAME
    if not header_path.is_file() or not footer_path.is_file():
        raise _preflight_prompt_error(f"no shared smallest-proof-boundary guidance at {header_path}")
    style_path = prompts_dir() / WRITING_STYLE_PROMPT_FILENAME
    if not style_path.is_file():
        raise _preflight_prompt_error(f"no shared roadmap writing-style guidance at {style_path}")
    def unreadable_prompt_input(exc: OSError | UnicodeDecodeError) -> RoadmapEnvironmentalError:
        return RoadmapEnvironmentalError(
            f"roadmap stage {stage.number} ({stage.name}) prompt input is not "
            f"readable ({exc})"
        )

    header_text = read_roadmap_text(header_path, error_for_read_failure=unreadable_prompt_input)
    footer_text = read_roadmap_text(footer_path, error_for_read_failure=unreadable_prompt_input)
    template_text = read_roadmap_text(template_path, error_for_read_failure=unreadable_prompt_input)
    style_text = read_roadmap_text(style_path, error_for_read_failure=unreadable_prompt_input)
    variables: dict[str, str] = {
        "slug": slug,
        "writing_style": style_text.rstrip(),
        "brief": _CARRIED_DECISIONS_SECTION.sub("", brief).rstrip() + "\n",
        "smallest_proof_boundary_header": header_text,
        "smallest_proof_boundary_footer": footer_text,
        "inherited_decisions": json.dumps(
            [
                {
                    "id": decision.id,
                    "chosen_option": decision.chosen_option,
                    "anchor": decision.anchor,
                    "status": "settled",
                    "source": decision.source,
                    "rationale": decision.rationale,
                    "rejected_alternatives": [
                        {"option": item.option, "reason": item.reason}
                        for item in decision.rejected_alternatives
                    ],
                }
                for decision in (carried_decisions.decisions if carried_decisions else ())
                if decision.owner == stage.artifact_key
            ],
            indent=2,
            sort_keys=True,
        ),
    }
    for loaded in upstream:
        variables[f"{loaded.stage.artifact_key}_artifact"] = loaded.text
    # ``safe_substitute`` so markdown braces in a template pass through
    # untouched, matching ``renderer.render_prompt``.
    authoring_prompt = Template(template_text).safe_substitute(variables)
    return authoring_prompt


def render_update_judgment_section(authority_clause: str) -> str:
    """Render the shared single-item "Update judgment" guidance.

    The local and structural revision prompts differ only in how authority is
    granted (an allowed presentation field vs. an issued structural
    operation); every other word is identical, so both render from this one
    source rather than carrying their own hand-copied section.
    """
    template_path = prompts_dir() / UPDATE_JUDGMENT_PROMPT_FILENAME
    if not template_path.is_file():
        raise RoadmapError(f"no shared update-judgment guidance at {template_path}")
    return Template(template_path.read_text(encoding="utf-8")).substitute(
        authority_clause=authority_clause
    )


def _render_stage_feedback_prompt(context: Any) -> str:
    """Render the closed operation request from the issued stage context only."""
    template_path = prompts_dir() / STAGE_FEEDBACK_REVISION_PROMPT_FILENAME
    if not template_path.is_file():
        raise _preflight_prompt_error(f"no bounded stage feedback prompt template at {template_path}")
    shared_guidance_path = prompts_dir() / REVISION_PROMPT_FILENAME
    if not shared_guidance_path.is_file():
        raise _preflight_prompt_error(f"no shared roadmap revision guidance at {shared_guidance_path}")
    def unreadable_prompt_input(exc: OSError | UnicodeDecodeError) -> RoadmapEnvironmentalError:
        return RoadmapEnvironmentalError(
            f"bounded stage feedback prompt input is not readable ({exc})"
        )

    shared_guidance_text = read_roadmap_text(
        shared_guidance_path, error_for_read_failure=unreadable_prompt_input
    )
    template_text = read_roadmap_text(template_path, error_for_read_failure=unreadable_prompt_input)
    variables = {
        "shared_revision_guidance": shared_guidance_text,
        "context_json": json.dumps(_prompt_json_value(context), indent=2, sort_keys=True),
        "operation_schema": json.dumps(
            _StageRevisionEnvelope.model_json_schema(), indent=2, sort_keys=True
        ),
        "max_active_feedback_items": str(context.limits.max_active_feedback_items),
        "max_response_bytes": str(context.limits.max_response_bytes),
        "max_prose_amendment_bytes": str(context.limits.max_prose_amendment_bytes),
        "max_material_operations_per_feedback": str(STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK),
    }
    try:
        return Template(template_text).substitute(variables)
    except KeyError as exc:
        raise _preflight_prompt_error(
            f"bounded stage feedback prompt has an unresolved placeholder {exc.args[0]!r}"
        ) from exc
    except ValueError as exc:
        raise _preflight_prompt_error(
            "bounded stage feedback prompt has a malformed placeholder"
        ) from exc


def _prompt_json_value(value: Any) -> Any:
    """Convert typed context values without retaining the source artifact text."""
    unwrapped = unwrap_enum_value(value)
    if unwrapped is not value:
        return _prompt_json_value(unwrapped)
    if dataclasses.is_dataclass(value):
        return {
            field.name: _prompt_json_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _prompt_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_prompt_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_prompt_json_value(item) for item in sorted(value)]
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    return value


def _strip_reply_lines(
    reply: str, *, strip_unpaired_trailing_fence: bool = False
) -> list[str]:
    """Fail closed on ambiguous preamble fences unless unpaired stripping is
    enabled, then conditionally strip a trailing fence.

    ``strip_unpaired_trailing_fence`` defaults ``False`` — both real
    callers (``_run_stage``, ``_materialize_plan_seed``) pass it explicitly,
    since ``True`` would truncate an artifact that legitimately ends its
    own real content on a closing code fence (see ``cacb256b``). It exists
    only for a caller that has independent reason to believe a lone
    trailing fence is *always* an unpaired wrapper leftover on its inputs,
    never genuine content — no current caller is in that position.

    An opening fence is an outer wrapper only when its unmatched opener is
    the last nonblank preamble line before frontmatter. An unclosed opener
    earlier in the preamble is ambiguous: it could be wrapper commentary or
    an illustrative fence, so this helper returns no lifted artifact and the
    caller retries rather than silently choosing which trailing fence to drop.

    Known residual gap, deliberately not chased further here: this only
    protects the *opener* decision. The separate "find the first ``---``"
    search in :func:`_lift_artifact_text` has no fence-awareness of its
    own, so a preamble containing an illustrative fenced example with its
    own "---"-delimited content ahead of the real artifact can still mislead
    it — excluding fenced spans from *that* search was tried and reverted
    because a genuine whole-reply wrapper (the common, tested case) fences
    the real frontmatter too, making its "---" indistinguishable from one
    inside an unrelated illustrative example under a naive "not inside any
    fenced span" rule. A correct fix needs to special-case "the fence wraps
    everything, including the frontmatter" from "the fence is truly
    unrelated content" — not attempted here; the stage's own parse/gate
    retry loop is the backstop for whatever this narrower gap misses.
    """
    text = reply.strip()
    if not text:
        return []
    lines = text.splitlines()
    frontmatter_at = next(
        (i for i, line in enumerate(lines) if line.rstrip() == _FRONTMATTER_FENCE),
        len(lines),
    )
    preamble = "\n".join(lines[:frontmatter_at])
    preamble_scan = _fenced_code_spans(preamble)
    last_preamble_line_start = preamble.rstrip().rfind("\n") + 1
    unmatched_opening = preamble_scan.unmatched_opening
    has_outer_opener = unmatched_opening == last_preamble_line_start
    if (
        unmatched_opening is not None
        and not has_outer_opener
        and not strip_unpaired_trailing_fence
    ):
        return []
    outer_opening_match = (
        _FENCE_OPEN_RE.match(preamble[unmatched_opening:].splitlines()[0])
        if has_outer_opener and unmatched_opening is not None
        else None
    )
    closing_match = (
        _FENCE_CLOSE_RE.match(lines[-1].rstrip("\r\n")) if lines else None
    )
    if closing_match is not None and (
        strip_unpaired_trailing_fence
        or (
            outer_opening_match is not None
            and _fence_run_closes(
                outer_opening_match.group(1)[0],
                len(outer_opening_match.group(1)),
                closing_match.group(1),
            )
        )
    ):
        lines = lines[:-1]
    return lines


def _lift_artifact_text(
    reply: str, *, strip_unpaired_trailing_fence: bool = False
) -> Optional[str]:
    """Pull the artifact text out of a stage reply, or ``None``.

    Tolerant here, strict at the module boundary: a model adds preamble and
    code fences, so everything before the first ``---`` line is skipped and a
    final fence is conditionally stripped
    (``detail.parse_detail_response`` is the precedent). What comes back is
    handed to the stage's own parser unchanged — the tolerance stops here.
    """
    lines = _strip_reply_lines(
        reply, strip_unpaired_trailing_fence=strip_unpaired_trailing_fence
    )
    if not lines:
        return None
    start = next(
        (index for index, line in enumerate(lines) if line.rstrip() == _FRONTMATTER_FENCE),
        None,
    )
    if start is None:
        return None
    lifted = "\n".join(lines[start:]).strip()
    return f"{lifted}\n" if lifted else None


# --------------------------------------------------------------------------
# Reading and writing artifacts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _LoadedArtifact:
    """One artifact as it sits on disk: its stage, its bytes, its parse.

    The text and the parsed value come from the same read, so a stage's prompt
    map and its gate envelope can never disagree about what is on disk.
    """

    stage: RoadmapStage
    path: Path
    text: str
    artifact: Any


class RoadmapSourceAdmissionError(ValueError):
    """A re-entered artifact no longer matches its trusted semantic source."""

    def __init__(self, stage: RoadmapStage, detail: str) -> None:
        self.stage = stage
        super().__init__(detail)


def load_accepted_roadmap_artifacts(*, plans_dir: Path, slug: str) -> tuple[_LoadedArtifact, ...]:
    """Parse the four stage artifacts from the accepted version's stored bytes.

    Never falls back to top-level files; no accepted head raises
    :class:`NoPublishedRoadmapVersionError`.
    """
    try:
        version = load_accepted_version(plans_dir=plans_dir, slug=slug)
    except RoadmapVersionError as exc:
        raise RoadmapError(str(exc)) from exc
    if version is None:
        raise NoPublishedRoadmapVersionError(no_published_version_message(plans_dir, slug))
    version_dir = version_directory_path(plans_dir, slug, version.record.version_id)
    loaded: list[_LoadedArtifact] = []
    for stage, data in zip(STAGES, version.artifact_bytes, strict=True):
        path = version_dir / artifact_member_name(stage.artifact_key)
        try:
            text = data.decode("utf-8")
            artifact = stage.parse(text)
        except (RoadmapArtifactError, UnicodeDecodeError) as exc:
            raise RoadmapArtifactError(f"{path}: {exc}", path=path) from exc
        loaded.append(_LoadedArtifact(stage=stage, path=path, text=text, artifact=artifact))
    return tuple(loaded)


def load_accepted_plans_artifact(*, plans_dir: Path, slug: str) -> PlansArtifact:
    """Return the accepted version's plans artifact (stage 4)."""
    artifact = load_accepted_roadmap_artifacts(plans_dir=plans_dir, slug=slug)[-1].artifact
    if not isinstance(artifact, PlansArtifact):  # Defensive against a custom stage table.
        raise RoadmapError("roadmap seed routes require a plans artifact at stage 4")
    return artifact


def recheck_feedback_snapshot(predecessor: _LoadedArtifact, expected: object) -> None:
    """Keep reviewer-owned rows stable for one bounded feedback attempt."""
    try:
        current = predecessor.stage.parse(predecessor.path.read_text(encoding="utf-8"))
        observed = feedback_snapshot(current)
    except (OSError, UnicodeError, RoadmapArtifactError, RoadmapSourceIdentityError) as exc:
        raise RoadmapSourceAdmissionError(
            predecessor.stage,
            f"stage {predecessor.stage.number} ({predecessor.stage.name}) feedback cannot be rechecked",
        ) from exc
    if observed != expected:
        raise RoadmapSourceAdmissionError(
            predecessor.stage,
            "concurrent reviewer feedback changed after preflight; refuse the stale revision",
        )


def _check_predecessor_review_rows(loaded: _LoadedArtifact) -> None:
    """The two reviewer-authored predecessor defects, raised before any call.

    Both are the reviewer's to fix and no retry could. A duplicate feedback id
    leaves "the predecessor's row for this id" undefined for every gate rule
    that joins on it, and parse time deliberately lets it through. An
    unresolvable ``row`` target can only be repaired by editing the reviewer's
    own ``target``, which ``VIOLATION_ALTERED_FEEDBACK_SOURCE`` forbids. Either
    one would spend a stage's whole budget writing nothing.

    Target resolvability belongs to ``check_feedback_integrity`` because it
    must also cover carried review rows on every re-gate route.
    """
    artifact = loaded.artifact
    feedback = tuple(getattr(artifact, "feedback", ()))

    counts: dict[str, int] = {}
    for row in feedback:
        counts[row.id] = counts.get(row.id, 0) + 1
    for row in feedback:
        if counts[row.id] > 1:
            raise RoadmapError(
                f"{loaded.path} carries {counts[row.id]} feedback rows with id "
                f"'{row.id}' — a feedback id names one request, and every rule "
                f"joining a revision to the version it replaces would resolve "
                f"it two ways; keep one row per id"
            )

    # Stage feedback has a richer authority matrix than the local selector:
    # the typed stage context validates hosting and retained-store targets.
    # Keep this early check to duplicate ids only; target authority belongs to
    # ``build_stage_revision_context``.


def _build_envelope(
    entries: Sequence[_LoadedArtifact],
    *,
    predecessor: Optional[_LoadedArtifact] = None,
    carried_decisions: CarriedDecisions | None = None,
) -> ArtifactEnvelope:
    """The gate envelope for the last entry: it plus everything below it.

    Filled the same way for every stage — by ``artifact_key``, from artifacts
    loaded off disk — so the loop never learns which gate needs what.

    ``predecessor`` is the prior version of the *last* entry and rides its own
    keyword rather than the sequence: it shares an ``artifact_key`` with the
    artifact under check, so the comprehension would drop one of the two. A
    first run leaves it defaulted, which keeps the revision gates inert: there
    is nothing it is a revision of.
    """
    return ArtifactEnvelope(
        predecessor=None if predecessor is None else predecessor.artifact,
        carried_decisions=carried_decisions,
        **{entry.stage.artifact_key: entry.artifact for entry in entries},
    )


def _pending_decision_count(artifact: Any) -> int:
    """``pending`` decision rows on one artifact.

    Reads the ``decisions`` collection every roadmap artifact carries rather
    than asking which artifact this is — a per-stage counter would be the
    identity branch the table exists to remove.
    """
    return sum(
        1
        for row in getattr(artifact, "decisions", ())
        if getattr(row, "status", None) == DecisionStatus.PENDING
    )


def _awaiting_review_count(artifact: Any) -> int:
    """``awaiting-review`` feedback rows on one artifact.

    Counts rows carried in from an earlier run as well as ones this run
    answered: a row that has waited through two runs waits for the same human,
    and telling the two apart would need a predecessor comparison no consumer
    asked for.
    """
    return sum(
        1
        for row in getattr(artifact, "feedback", ())
        if getattr(row, "state", None) == FeedbackState.AWAITING_REVIEW
    )


def _newly_settled_decision_ids(
    artifact: Any, predecessor: Optional["_LoadedArtifact"]
) -> tuple[str, ...]:
    """Decision ids this revision settled and the predecessor had not, in
    artifact order.

    Two shapes, one predicate: a row the predecessor never carried, and one it
    carried as ``pending``. Both confer the fence, and
    :func:`~plan_tool.roadmap_gates.check_settled_decisions` — which examines
    only rows *already* ``settled`` in the predecessor — pins either with equal
    force on the next run. The flip is the quieter shape, because it also drops
    the row out of ``pending_decisions``.

    Predecessor-only: a first run authors the initial fence with no human prior
    to contradict. Binary observable — ``settled`` here, not ``settled`` there.
    Whether the reviewer settled it is semantic and stays their call; this only
    names the ids (CLAUDE.md § "Validating a semantic property you cannot
    observe").
    """
    if predecessor is None:
        return ()
    prior_status = {
        row.id: getattr(row, "status", None)
        for row in getattr(predecessor.artifact, "decisions", ())
    }
    return tuple(
        row.id
        for row in getattr(artifact, "decisions", ())
        if getattr(row, "status", None) == DecisionStatus.SETTLED
        and prior_status.get(row.id) != DecisionStatus.SETTLED
    )


def _feedback_counts_by_state(artifact: Any) -> dict[str, int]:
    """One count per lifecycle state, zeros included.

    Every state is always a key, so a reader of a single run-log line indexes it
    without a ``.get`` — ``counts_by_state[FeedbackState.OPEN.value]`` recovers
    the active subset unconditionally. A sparse map would make an absent key
    mean "zero" here and "unknown" everywhere else.
    """
    counts = {state.value: 0 for state in FeedbackState}
    for row in getattr(artifact, "feedback", ()):
        counts[row.state.value] += 1
    return counts


def _has_open_feedback(loaded: Optional[_LoadedArtifact]) -> bool:
    """Whether this predecessor is applying reviewer feedback this run."""
    return loaded is not None and any(
        row.state is FeedbackState.OPEN for row in getattr(loaded.artifact, "feedback", ())
    )


def _load_roadmap_seed_state(*, plans_dir: Path, slug: str) -> dict[str, Any]:
    """Read one roadmap's sidecar as a roadmap-shaped preflight failure."""
    path = seed_state_path(roadmap_dir(plans_dir, slug))
    try:
        return load_seed_state(path)
    except RoadmapSeedStateError as exc:
        raise RoadmapError(str(exc)) from exc


def _write_roadmap_seed_state(state: Mapping[str, Any], *, plans_dir: Path, slug: str) -> None:
    """Persist one roadmap's sidecar while retaining one error vocabulary."""
    path = seed_state_path(roadmap_dir(plans_dir, slug))
    try:
        write_seed_state(path, state)
    except RoadmapSeedStateError as exc:
        raise RoadmapError(str(exc)) from exc


# --------------------------------------------------------------------------
# The attempt loop
# --------------------------------------------------------------------------


def _note_stage_attempt_failure(
    run_logger: Optional[RunLoggerLike],
    *,
    phase: str,
    stage: RoadmapStage,
    attempt: int,
    failed: _StageOutcome,
) -> None:
    """Record every retry-spending outcome through the shared event shape."""
    if run_logger is not None and failed.failure_kind is not None:
        run_logger.attempt_failed(
            phase=phase,
            attempt=attempt,
            failure_kind=failed.failure_kind,
            stage=stage.number,
        )


# Receipt reasons for a rejected reply that ends the attempt immediately
# rather than consuming one of the four failure kinds above — shared by
# every producer's receipt via ``record_model_failure_receipt``.
REASON_SOURCE_ADMISSION_REJECTED = "source-admission-rejected"
REASON_INVALID_DETAIL = "invalid_detail"


def record_model_failure_receipt(
    run_logger: Optional[RunLoggerLike],
    *,
    slug: str,
    phase: str,
    attempt: int,
    reason: str,
    reply: str | None,
    retain_response: bool = True,
) -> None:
    """Persist one rejected reply's safe identity and availability.

    Shared by every roadmap-family producer so byte count, digest, sidecar
    storage, and receipt emission stay one implementation.
    """
    if run_logger is None:
        return

    # An empty reply has no response identity. Whitespace is a real rejected
    # response and must remain distinguishable from absence.
    raw_response = reply if reply else None
    repo_root = getattr(run_logger, "repo_root", None)
    if repo_root is None:
        return
    run_id = getattr(run_logger, "run_id", "run")
    sidecar_result = store_model_response_sidecar(
        repo_root=Path(repo_root),
        # A leading underscore rules out a collision with any create-minted
        # plan slug (SLUG_RE forbids it) — unlike a plain "roadmap" segment,
        # which one could still hit. It does NOT rule out a register-
        # adopted plan (register never validates the slug it derives from
        # the on-disk filename): see BUG_BACKLOG.md "No fixed producer_slug
        # prefix can structurally rule out a sidecar-directory collision
        # with a register-adopted plan".
        producer_slug=f"_roadmap/{slug}",
        receipt_identity=f"{run_id}-{phase}-attempt{attempt}",
        raw_response=raw_response,
        retain_response=retain_response,
    )
    run_logger.model_failure_receipt(
        phase=phase,
        attempt=attempt,
        reason=reason,
        response_bytes=sidecar_result.response_bytes,
        response_sha256=sidecar_result.digest,
        sidecar_result=sidecar_result,
    )


@dataclass(frozen=True)
class _StageOutcome:
    """What one stage's attempt loop produced.

    ``artifact`` is set only when the stage cleared its gates; every other
    field describes the attempt that spent the last of the budget.
    """

    artifact: Any = None
    violations: tuple[Violation, ...] = ()
    failure_kind: Optional[str] = None
    failure_rc: Optional[int] = None
    failure_detail: Optional[str] = None
    invalid_detail: Optional[str] = None
    reused_predecessor: bool = False


def _reply_head(reply: str) -> str:
    """The front of a reply, for a diagnostic a caller can print in one line."""
    return reply.strip()[:_REPLY_HEAD_CHARS]


def _authored_review_rows(artifact: Any) -> tuple[str, ...]:
    """The review rows in ``artifact``, named; a first run has none to carry, so any is invented.

    No gate rejects an invented feedback row, and a removal record is grounded
    only against a predecessor, so a fabricated one would land as carried
    history no later revision re-judges.
    """
    authored = [f"feedback row '{row.id}'" for row in getattr(artifact, "feedback", ())]
    authored.extend(
        f"removal record for '{record.removed_id}'"
        for record in getattr(artifact, "removals", ())
    )
    return tuple(authored)


def _run_stage(
    stage: RoadmapStage,
    *,
    slug: str,
    brief: str,
    upstream: Sequence[_LoadedArtifact],
    invoker: StageInvoker,
    max_attempts: int,
    run_logger: Optional[RunLoggerLike],
    phase: str,
    source_recheck: Callable[[], None] | None = None,
    status_callback: StatusCallback | None = None,
    carried_decisions: CarriedDecisions | None = None,
) -> _StageOutcome:
    """Call, lift, parse, gate — up to ``max_attempts`` times.

    One retry channel, four failure kinds: a non-zero rc or empty reply, an
    unliftable or unparseable reply, a reply authoring review rows the reviewer
    never wrote, and gate violations all consume an attempt and all feed the
    same corrections block, because an operator experiences them identically.
    The *report* still distinguishes them — see :class:`RoadmapResult`.

    The authored-review-rows refusal sits here rather than at the write because
    this loop is the only place that knows a *model* produced the bytes under
    check: it is entered once per attempt from the stage loop, and it already
    owns the correction channel the refusal needs. A held stage is re-gated
    with the same refusal in :func:`_held_stage_regate_failure`.

    This loop creates fresh artifacts only.
    """
    try:
        if source_recheck is not None:
            source_recheck()
        base_prompt = _render_stage_prompt(
            stage,
            slug=slug,
            brief=brief,
            upstream=upstream,
            carried_decisions=carried_decisions,
        )
    except RoadmapSourceAdmissionError as exc:
        return _StageOutcome(invalid_detail=str(exc))
    outcome = _StageOutcome()
    corrections: tuple[str, ...] = ()

    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1 and source_recheck is not None:
                source_recheck()
        except RoadmapSourceAdmissionError as exc:
            return _StageOutcome(invalid_detail=str(exc))
        prompt = base_prompt
        if corrections:
            prompt += _corrections_block(corrections)

        if run_logger is not None:
            run_logger.claude_call_start(
                phase=phase,
                attempt=attempt,
                prompt_bytes=len(prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(prompt),
                stage=stage.number,
            )
            sink = run_logger.bind_shell_sink(phase=phase, attempt=attempt)
        else:
            sink = contextlib.nullcontext()
        _emit_stage_retry_status(
            status_callback,
            slug=slug,
            stage=stage,
            attempt=attempt,
            failure_kind=outcome.failure_kind,
        )
        with sink:
            rc, reply = invoker(prompt)

        if rc != 0 or not reply.strip():
            outcome = _StageOutcome(
                failure_kind=FAILURE_INVOKE,
                failure_rc=rc,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_INVOKE,
                reply=reply,
            )
            corrections = (
                f"the previous attempt produced no usable reply (exit code "
                f"{rc}) — reply with the artifact text and nothing else",
            )
            continue

        lifted = _lift_artifact_text(reply, strip_unpaired_trailing_fence=False)
        if lifted is None:
            outcome = _StageOutcome(
                failure_kind=FAILURE_PARSE,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_PARSE,
                reply=reply,
            )
            corrections = (
                f"the previous response carried no artifact: it must open on a "
                f"'{_FRONTMATTER_FENCE}' frontmatter fence, hold the row "
                f"inventory as YAML, close the fence, and continue with the "
                f"prose body",
            )
            continue

        try:
            artifact = stage.parse(lifted)
        except RoadmapArtifactError as exc:
            outcome = _StageOutcome(
                failure_kind=FAILURE_PARSE,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_PARSE,
                reply=reply,
            )
            corrections = (f"the previous response was off contract: {exc}",)
            continue

        authored = _authored_review_rows(artifact)
        if authored:
            outcome = _StageOutcome(
                failure_kind=FAILURE_AUTHORED_REVIEW_ROWS,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_AUTHORED_REVIEW_ROWS,
                reply=reply,
            )
            corrections = (
                f"the previous response authored review rows the reviewer never "
                f"wrote ({', '.join(authored)}) — a first run has no feedback or "
                f"removals; drop the 'feedback' and 'removals' entries",
            )
            continue

        try:
            if source_recheck is not None:
                source_recheck()
        except RoadmapSourceAdmissionError as exc:
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=REASON_SOURCE_ADMISSION_REJECTED,
                reply=reply,
            )
            return _StageOutcome(invalid_detail=str(exc))
        envelope = _build_envelope(
            [*upstream, _staged(stage, artifact)],
            carried_decisions=carried_decisions,
        )
        violations = tuple(stage.gates(envelope))
        if not violations:
            return _StageOutcome(artifact=artifact)
        outcome = _StageOutcome(
            failure_kind=FAILURE_GATES,
            violations=violations,
        )
        violation_messages = tuple(v.message for v in violations)
        corrections = violation_messages
        _note_stage_attempt_failure(
            run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
        )
        if run_logger is not None:
            # From the violations, not from ``corrections``: the event's field
            # is named ``violations``, so it must stay what the gates said even
            # if the corrections block later reshapes them.
            run_logger.gate_violations(
                phase=phase,
                attempt=attempt,
                messages=violation_messages,
                stage=stage.number,
            )
        record_model_failure_receipt(
            run_logger,
            slug=slug,
            phase=phase,
            attempt=attempt,
            reason=FAILURE_GATES,
            reply=reply,
            retain_response=False,
        )

    return outcome


def _run_bounded_stage_feedback(
    stage: RoadmapStage,
    *,
    slug: str,
    predecessor: _LoadedArtifact,
    upstream: Sequence[_LoadedArtifact],
    limits: StageFeedbackLimits,
    invoker: StageInvoker,
    max_attempts: int,
    run_logger: Optional[RunLoggerLike],
    phase: str,
    status_callback: StatusCallback | None = None,
    carried_decisions: CarriedDecisions | None = None,
) -> _StageOutcome:
    """Apply one closed operation envelope per active reviewer request."""
    snapshot = feedback_snapshot(predecessor.artifact)
    try:
        recheck_feedback_snapshot(predecessor, snapshot)
        context = build_stage_revision_context(
            predecessor.artifact,
            {entry.stage.artifact_key: entry.artifact for entry in upstream},
            limits,
            artifact_key=stage.artifact_key,
        )
        prompt = _render_stage_feedback_prompt(context)
    except StageRevisionLimitError as exc:
        return _StageOutcome(invalid_detail=str(exc))
    except (RevisionContractError, RoadmapArtifactError, RoadmapSourceAdmissionError) as exc:
        return _StageOutcome(invalid_detail=str(exc))

    corrections: tuple[str, ...] = ()
    outcome = _StageOutcome()

    def guard() -> None:
        recheck_feedback_snapshot(predecessor, snapshot)

    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                guard()
        except RoadmapSourceAdmissionError as exc:
            return _StageOutcome(invalid_detail=str(exc))
        attempt_prompt = prompt + (
            _stage_feedback_corrections_block(corrections) if corrections else ""
        )
        if run_logger is not None:
            run_logger.claude_call_start(
                phase=phase,
                attempt=attempt,
                prompt_bytes=len(attempt_prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(attempt_prompt),
                stage=stage.number,
            )
            sink = run_logger.bind_shell_sink(phase=phase, attempt=attempt)
        else:
            sink = contextlib.nullcontext()
        _emit_stage_retry_status(
            status_callback,
            slug=slug,
            stage=stage,
            attempt=attempt,
            failure_kind=outcome.failure_kind,
        )
        with sink:
            rc, reply = invoker(attempt_prompt)
        if rc != 0 or not reply.strip():
            outcome = _StageOutcome(
                failure_kind=FAILURE_INVOKE,
                failure_rc=rc,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_INVOKE,
                reply=reply,
            )
            corrections = (f"the previous attempt produced no usable JSON reply (exit code {rc})",)
            continue
        try:
            operations = parse_stage_revision_operations(reply, context)
            candidate = merge_stage_feedback_revision(predecessor.artifact, context, operations)
        except (StageRevisionLimitError, StageRevisionSourceError) as exc:
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=REASON_INVALID_DETAIL,
                reply=reply,
            )
            return _StageOutcome(invalid_detail=str(exc))
        except (RevisionContractError, RevisionMergeError, RoadmapArtifactError) as exc:
            outcome = _StageOutcome(
                failure_kind=FAILURE_PARSE,
                failure_detail=_reply_head(reply),
            )
            _note_stage_attempt_failure(
                run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
            )
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=FAILURE_PARSE,
                reply=reply,
            )
            corrections = (f"the previous response was off contract: {exc}",)
            continue
        try:
            guard()
        except RoadmapSourceAdmissionError as exc:
            record_model_failure_receipt(
                run_logger,
                slug=slug,
                phase=phase,
                attempt=attempt,
                reason=REASON_SOURCE_ADMISSION_REJECTED,
                reply=reply,
            )
            return _StageOutcome(invalid_detail=str(exc))
        violations = tuple(
            stage.gates(
                _build_envelope(
                    [*upstream, _staged(stage, candidate)],
                    predecessor=predecessor,
                    carried_decisions=carried_decisions,
                )
            )
        )
        if not violations:
            return _StageOutcome(artifact=candidate)
        outcome = _StageOutcome(failure_kind=FAILURE_GATES, violations=violations)
        _note_stage_attempt_failure(
            run_logger, phase=phase, stage=stage, attempt=attempt, failed=outcome
        )
        corrections = tuple(item.message for item in violations)
        if run_logger is not None:
            run_logger.gate_violations(
                phase=phase,
                attempt=attempt,
                messages=corrections,
                stage=stage.number,
            )
        record_model_failure_receipt(
            run_logger,
            slug=slug,
            phase=phase,
            attempt=attempt,
            reason=FAILURE_GATES,
            reply=reply,
            retain_response=False,
        )
    return outcome


def _run_feedback_free_stage(
    stage: RoadmapStage,
    *,
    predecessor: _LoadedArtifact,
    upstream: Sequence[_LoadedArtifact],
    feedback_snapshot_before: object,
    carried_decisions: CarriedDecisions | None = None,
) -> _StageOutcome:
    """Re-gate an admitted feedback-free predecessor without publishing it."""
    try:
        recheck_feedback_snapshot(predecessor, feedback_snapshot_before)
        violations = tuple(
            stage.gates(
                _build_envelope(
                    [*upstream, predecessor],
                    predecessor=predecessor,
                    carried_decisions=carried_decisions,
                )
            )
        )
    except RoadmapSourceAdmissionError as exc:
        return _StageOutcome(invalid_detail=str(exc))
    return _StageOutcome(
        artifact=predecessor.artifact,
        violations=violations,
        reused_predecessor=not violations,
    )


def _staged(stage: RoadmapStage, artifact: Any) -> _LoadedArtifact:
    """An in-memory artifact wrapped for envelope building (never written)."""
    return _LoadedArtifact(stage=stage, path=Path(), text="", artifact=artifact)


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------


def _brief_reference(brief_path: Path, *, repo_root: Path) -> str:
    """Render ``brief_path`` portably when it sits below ``repo_root``."""
    resolved = Path(brief_path).resolve()
    try:
        return resolved.relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _error_run_end_fields(failure: Optional[BaseException]) -> tuple[int, Optional[str]]:
    """The ``(rc, error)`` pair for an owned writer's failure-arm ``run_end``.

    An operator's Ctrl-C reports ``rc=130``/``"interrupted"`` — matching
    ``cli/run_cmd.py``'s wording — instead of the generic ``rc=1`` with
    ``str(KeyboardInterrupt())``'s empty string, which reads as an
    unexplained crash. Every other failure keeps that generic shape.
    """
    if isinstance(failure, KeyboardInterrupt):
        return 130, "interrupted"
    return 1, (str(failure) if failure is not None else None)


@dataclass
class _RoadmapCommandLifecycle:
    """Track one roadmap command's effective logger and terminal result."""

    run_logger: RunLoggerLike
    outcome: str | None = None
    rc: int | None = None

    def complete(self, *, outcome: str, rc: int) -> None:
        """Record the command-specific terminal result for owned cleanup."""
        self.outcome = outcome
        self.rc = rc


@contextlib.contextmanager
def _roadmap_command_lifecycle(
    *,
    repo_root: Path,
    plans_dir: Path,
    slug: str,
    run_logger: Optional[RunLoggerLike],
    flags: dict[str, Any],
    context: Optional[Mapping[str, Any]] = None,
) -> Iterator[_RoadmapCommandLifecycle]:
    """Own a command-created roadmap writer through its terminal path.

    Validates ``slug`` against ``plans_dir`` before anything turns it into a
    filesystem path — the one guard every caller needs, owned here once
    instead of hand-rolled ahead of each call site.
    """
    try:
        roadmap_dir(plans_dir, slug)
    except ValueError as exc:
        raise RoadmapError(str(exc)) from exc

    owned_logger: RunLogWriter | None = None
    if run_logger is None:
        owned_logger = RunLogWriter.start(
            repo_root=repo_root,
            slug=slug,
            command="roadmap",
            argv=[],
            flags=flags,
            context=context,
        )
        run_logger = owned_logger

    lifecycle = _RoadmapCommandLifecycle(run_logger=run_logger)
    failure: BaseException | None = None
    try:
        yield lifecycle
    except BaseException as exc:
        failure = exc
        if isinstance(exc, (RoadmapError, RoadmapArtifactError)) and not hasattr(
            exc, "roadmap_stage_started"
        ):
            # The CLI needs the same origin fact as this owned run-end path.
            exc.roadmap_stage_started = False
        raise
    finally:
        if owned_logger is not None:
            if lifecycle.outcome is None:
                if (
                    isinstance(failure, (RoadmapError, RoadmapArtifactError))
                    and not getattr(failure, "roadmap_stage_started", False)
                ):
                    outcome = "preflight-refused"
                    rc, error_message = 2, None
                else:
                    outcome = "error"
                    rc, error_message = _error_run_end_fields(failure)
            else:
                outcome = lifecycle.outcome
                rc = lifecycle.rc
                error_message = None
            if rc is None:
                # Defensive: `complete()` is typed to require an int. Fall
                # back rather than raise here, which would replace whatever
                # exception is unwinding through this `finally` with an
                # unrelated one.
                rc = 1
            owned_logger.run_end(
                outcome=outcome,
                rc=rc,
                error=error_message,
            )


def _held_stage_regate_failure(
    stage: RoadmapStage,
    text: str,
    *,
    held_upstream: Sequence[_LoadedArtifact],
    carried_decisions: CarriedDecisions,
) -> tuple[Any, str | None]:
    """Parse and re-gate one held stage in memory: ``(artifact, None)`` or ``(None, reason)``."""
    try:
        artifact = stage.parse(text)
    except RoadmapArtifactError as exc:
        return None, f"no longer parses ({exc})"
    authored = _authored_review_rows(artifact)
    if authored:
        return None, f"carries review rows no reviewer wrote ({', '.join(authored)})"
    violations = tuple(
        stage.gates(
            _build_envelope(
                [*held_upstream, _staged(stage, artifact)], carried_decisions=carried_decisions
            )
        )
    )
    if violations:
        return None, "fails its own checks: " + "; ".join(v.message for v in violations)
    return artifact, None


def _pre_head_state_paths(*, plans_dir: Path, slug: str) -> tuple[Path, ...]:
    """Every pre-head roadmap path found under ``slug``'s folder, in a fixed order."""
    root = roadmap_dir(plans_dir, slug)
    if not root.is_dir():
        return ()
    found: list[Path] = sorted(root.glob("[0-9][0-9]-*.md"))
    for single_file in (roadmap_feedback_ledger_path(plans_dir, slug), seed_state_path(root)):
        if single_file.exists() or single_file.is_symlink():
            found.append(single_file)
    for directory in (
        version_namespace_path(plans_dir, slug),
        root / DRAFT_SEEDS_DIRNAME,
        root / LEGACY_DRAFT_SEEDS_DIRNAME,
    ):
        # An emptied directory is what a rolled-back root generation leaves
        # behind; only a stored file is state. An interrupted durable write's
        # temp leftover is not stored.
        if directory.is_dir() and any(
            entry.is_file() and not is_write_temp_name(entry.name)
            for entry in directory.rglob("*")
        ):
            found.append(directory)
    return tuple(found)


def stage_resume_directory(repo_root: Path, slug: str) -> Path:
    """The first-run resume directory, for operator-facing text outside the stage run."""
    return resume_dir_path(repo_root, slug)


def _delete_resume_or_warn(repo_root: Path, slug: str, *, outcome: str) -> None:
    """Delete the resume directory; a failure warns, since the head already decided the outcome."""
    try:
        delete_resume(repo_root, slug)
    except OSError as exc:
        print(
            f"warning: roadmap {slug}: {outcome}, but could not delete the "
            f"resume directory ({exc})",
            file=sys.stderr,
        )


def _require_no_accepted_head(
    *, repo_root: Path, plans_dir: Path, slug: str, run_logger: Optional[RunLoggerLike]
) -> None:
    """Refuse a stage run beside an accepted head, discarding a stale resume directory."""
    try:
        head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    except RoadmapVersionError as exc:
        if run_logger is not None:
            run_logger.roadmap_preflight_failed(check="accepted_head")
        raise RoadmapHeadExistsError(
            f"roadmap {slug}: the accepted-head state at "
            f"{accepted_head_path(plans_dir, slug)} cannot be read ({exc}); a stage "
            "run cannot proceed beside it"
        ) from exc
    if head is None:
        return
    # A run that committed its head and crashed before cleanup leaves this behind.
    _delete_resume_or_warn(repo_root, slug, outcome="accepted head present")
    refresh_roadmap_index(plans_dir, slug)
    if run_logger is not None:
        run_logger.roadmap_preflight_failed(check="accepted_head")
    raise RoadmapHeadExistsError(
        f"roadmap {slug} already has an accepted head "
        f"({accepted_head_path(plans_dir, slug)}, version {head.version_id}); a roadmap "
        "with a head is changed through feedback and review, not through a stage run"
    )


def _require_no_pre_head_state(
    *, plans_dir: Path, slug: str, run_logger: Optional[RunLoggerLike]
) -> None:
    """Refuse a folder with no head that already holds roadmap files."""
    found = _pre_head_state_paths(plans_dir=plans_dir, slug=slug)
    if not found:
        return
    if run_logger is not None:
        run_logger.roadmap_preflight_failed(check="pre_head_state")
    listing = "\n".join(f"- {path}" for path in found)
    raise RoadmapPreHeadStateError(
        f"roadmap {slug} has no accepted head but its folder already holds:\n{listing}\n"
        "A stage run publishes into an empty folder, and no tool converts a folder "
        "like this; convert it by hand: move or delete the listed paths (deleting the "
        "feedback ledger discards its feedback rows) and run again, or start a "
        "successor slug."
    )


def _read_first_run_brief(
    *, brief_path: Path | None, slug: str, run_logger: Optional[RunLoggerLike]
) -> tuple[bytes, str]:
    """The brief's exact bytes and their text under the roadmap's text contract.

    One read feeds both, so the stored ``brief.md`` and the text the stages
    judge cannot differ; the text applies :func:`read_brief_text`'s
    universal-newline translation.
    """
    if brief_path is None:
        if run_logger is not None:
            run_logger.roadmap_preflight_failed(check="brief_source")
        raise RoadmapError(
            f"roadmap {slug}: no concept brief was given; pass --from-existing PATH"
        )
    try:
        brief_bytes = Path(brief_path).read_bytes()
        text = brief_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        return brief_bytes, text
    except (OSError, UnicodeDecodeError) as exc:
        if run_logger is not None:
            run_logger.roadmap_preflight_failed(check="brief_read")
        raise RoadmapError(
            f"roadmap brief is not readable at {brief_path} ({exc}); "
            "pass an existing concept brief with --from-existing"
        ) from exc


def _publish_root_version(
    *,
    slug: str,
    plans_dir: Path,
    writer_token: RoadmapWriterToken,
    brief_bytes: bytes,
    stages: Sequence[RoadmapStage],
    stage_texts: Mapping[int, str],
) -> str:
    """Publish one root generation (version, ledger, head last) and return its version id."""
    texts = tuple(stage_texts[stage.number] for stage in stages)
    snapshot = SimpleNamespace(
        brief_bytes=brief_bytes,
        brief_raw_digest=hashlib.sha256(brief_bytes).hexdigest(),
        artifact_keys=tuple(stage.artifact_key for stage in stages),
        artifact_texts=texts,
        artifact_digests=tuple(hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts),
    )
    try:
        prepared = prepare_root_version_from_snapshot(snapshot, roadmap_slug=slug)
        generation = build_root_enrollment_generation(prepared, plans_dir=plans_dir, slug=slug)
        generation = _with_initial_feedback_ledger(
            generation,
            plans_dir=plans_dir,
            slug=slug,
            ledger_state=LedgerState.LEDGER_NATIVE,
        )
        publish_roadmap_generation(
            generation, plans_dir=plans_dir, slug=slug, writer_token=writer_token
        )
        refresh_roadmap_index(plans_dir, slug)
    except (
        RoadmapVersionError,
        RoadmapPublicationRecoveryError,
        RoadmapRevisionPublishError,
    ) as exc:
        error = RoadmapError(f"roadmap {slug}: cannot publish the root version ({exc})")
        error.roadmap_stage_started = True
        raise error from exc
    return prepared.record.version_id


def run_roadmap(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    brief_path: Path | None = None,
    stages: Sequence[RoadmapStage] = STAGES,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_stage_attempts: int = MAX_STAGE_ATTEMPTS,
    run_logger: Optional[RunLoggerLike] = None,
    status_callback: StatusCallback | None = None,
) -> RoadmapResult:
    """Run a roadmap's first stage run while owning its writer guard."""
    primary_run_started = False
    try:
        with _roadmap_writer_owner(plans_dir, slug) as writer_token:
            primary_run_started = True
            return _run_roadmap(
                slug,
                repo_root=repo_root,
                plans_dir=plans_dir,
                brief_path=brief_path,
                stages=stages,
                invoker=invoker,
                max_stage_attempts=max_stage_attempts,
                run_logger=run_logger,
                status_callback=status_callback,
                writer_token=writer_token,
            )
    except (RoadmapWriterGuardError, RoadmapRevisionPublishError) as exc:
        if primary_run_started:
            raise RoadmapRunStartedWriterGuardError(str(exc)) from exc
        # Writer acquisition refused before `_run_roadmap` could create the
        # primary lifecycle, so close an owned preflight record here instead.
        with _roadmap_command_lifecycle(
            repo_root=Path(repo_root),
            plans_dir=Path(plans_dir),
            slug=slug,
            run_logger=run_logger,
            flags={},
        ) as lifecycle:
            lifecycle.complete(outcome="preflight-refused", rc=2)
            raise RoadmapError(str(exc)) from exc


def _run_roadmap(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    brief_path: Path | None = None,
    stages: Sequence[RoadmapStage] = STAGES,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_stage_attempts: int = MAX_STAGE_ATTEMPTS,
    run_logger: Optional[RunLoggerLike] = None,
    status_callback: StatusCallback | None = None,
    writer_token: RoadmapWriterToken | None = None,
) -> RoadmapResult:
    """Run ``slug``'s stages once and publish the root version after the last.

    Each gate-clean stage is held in memory and in the resume directory
    (:mod:`plan_tool.roadmap_stage_resume`); nothing else is written until every
    stage has passed, then one root generation publishes the version, a
    ledger-native ledger, and the accepted head (written last) and the resume
    directory is deleted. A failed run leaves only the resume directory, and the
    next run re-gates the held stages and continues after the last one that
    passes. An exhausted stage **halts the arc**: the next stage's invoker is
    never called. A stage table that is not the full version inventory (an
    injected test table) completes holding its stages and publishes nothing.
    See ``docs/how-to/roadmap.md``.

    Preflight order, each step before any model call: recover a pending root
    journal; refuse beside an accepted head; refuse a headless folder holding
    pre-head state; read the brief; refuse a changed brief.

    Raises :class:`RoadmapError` for anything that stops the run before it
    starts. Everything else comes back on a :class:`RoadmapResult`.
    """
    ordered = tuple(sorted(stages, key=lambda stage: stage.number))
    if writer_token is None:
        raise RoadmapError("roadmap stage publication requires the active writer guard")
    plans_dir = Path(plans_dir)
    repo_root = Path(repo_root)
    with _roadmap_command_lifecycle(
        repo_root=repo_root,
        plans_dir=plans_dir,
        slug=slug,
        run_logger=run_logger,
        flags={},
    ) as lifecycle:
        run_logger = lifecycle.run_logger
        try:
            recover_roadmap_publication(plans_dir=plans_dir, slug=slug, writer_token=writer_token)
        except (
            RoadmapWriterGuardError,
            RoadmapPublicationRecoveryError,
            RoadmapRevisionPublishError,
        ) as exc:
            if run_logger is not None:
                run_logger.roadmap_preflight_failed(check="publication_recovery")
            raise RoadmapError(str(exc)) from exc
        _require_no_accepted_head(
            repo_root=repo_root, plans_dir=plans_dir, slug=slug, run_logger=run_logger
        )
        _require_no_pre_head_state(plans_dir=plans_dir, slug=slug, run_logger=run_logger)
        brief_bytes, brief = _read_first_run_brief(
            brief_path=brief_path, slug=slug, run_logger=run_logger
        )
        current_brief_digest = digest_decoded_text(brief)
        held = read_held_stages(repo_root, slug)
        if held is not None:
            # File names only: the directory prefix would push the name past
            # the status line's length bound.
            directory_prefix = f"{held.directory}{os.sep}"
            for warning in held.warnings:
                _emit_roadmap_fact(
                    status_callback,
                    slug=slug,
                    fact=f"warning: {warning.removeprefix(directory_prefix)}",
                )
            try:
                require_matching_brief_digest(held, current_brief_digest)
            except RoadmapStageResumeBriefChanged as exc:
                if run_logger is not None:
                    run_logger.roadmap_preflight_failed(check="resume_brief_digest")
                raise RoadmapError(str(exc)) from exc
        try:
            carried_decisions = parse_carried_decisions(brief, brief_path=Path(brief_path))
        except RoadmapSourceError as exc:
            if run_logger is not None:
                run_logger.roadmap_preflight_failed(check="carried_decisions")
            raise RoadmapError(f"roadmap {slug}: {exc}") from exc

        held_texts: dict[int, str] = {}
        digest_on_disk = False
        if held is not None:
            if held.brief_digest is None:
                discard_stages_from(repo_root, slug, 1)
            else:
                held_texts = dict(held.stages)
                digest_on_disk = True
                # Files past the contiguous prefix are warned as not held; remove
                # them so a later run cannot re-gate them against new upstream.
                discard_stages_from(repo_root, slug, len(held.stages) + 1)

        stages_run: list[int] = []
        loaded: list[_LoadedArtifact] = []
        stage_texts: dict[int, str] = {}
        result: RoadmapResult | None = None
        resuming = bool(held_texts)

        _emit_accepted_stage_selection(status_callback, slug=slug, stages=ordered)

        for stage in ordered:
            phase = f"stage-{stage.number}-{stage.name}"
            if resuming and stage.number in held_texts:
                artifact, failure = _held_stage_regate_failure(
                    stage,
                    held_texts[stage.number],
                    held_upstream=loaded,
                    carried_decisions=carried_decisions,
                )
                if failure is None:
                    canonical_text = stage.render(artifact)
                    loaded.append(replace(_staged(stage, artifact), text=canonical_text))
                    stage_texts[stage.number] = canonical_text
                    _emit_roadmap_status(
                        status_callback, slug=slug, stage=stage, fact="re-gated without write"
                    )
                    continue
                held_file = resume_dir_path(repo_root, slug) / f"stage-{stage.number}.md"
                _emit_roadmap_fact(
                    status_callback,
                    slug=slug,
                    fact=f"warning: regenerating from stage {stage.number}: "
                    f"{held_file.name} {failure}",
                )
                discard_stages_from(repo_root, slug, stage.number)
            resuming = False

            started = time.monotonic()
            stages_run.append(stage.number)
            _emit_roadmap_status(status_callback, slug=slug, stage=stage, fact="started")
            with _stage_run_guard(status_callback, slug=slug, stage=stage) as stop_reporter:
                if run_logger is not None:
                    run_logger.phase_start(phase, stage=stage.number)
                outcome = _run_stage(
                    stage,
                    slug=slug,
                    brief=brief,
                    upstream=tuple(loaded),
                    invoker=invoker,
                    max_attempts=max_stage_attempts,
                    run_logger=run_logger,
                    phase=phase,
                    status_callback=status_callback,
                    carried_decisions=carried_decisions,
                )
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if outcome.artifact is None:
                    stop_reporter.emit(failure_kind=outcome.failure_kind)
                    if run_logger is not None:
                        run_logger.phase_end(phase, elapsed_ms, "exhausted")
                    result = RoadmapResult(
                        outcome=OUTCOME_STAGE_EXHAUSTED,
                        artifacts=(),
                        stages_run=tuple(stages_run),
                        pending_decisions=0,
                        failed_stage=stage.number,
                        violations=outcome.violations,
                        failure_kind=outcome.failure_kind,
                        failure_rc=outcome.failure_rc,
                        failure_detail=outcome.failure_detail,
                    )
                    break

                text = stage.render(outcome.artifact)
                try:
                    if not digest_on_disk:
                        write_brief_digest(repo_root, slug, current_brief_digest)
                        digest_on_disk = True
                    write_stage(repo_root, slug, stage.number, text)
                except OSError as exc:
                    raise RoadmapEnvironmentalError(
                        f"roadmap {slug}: cannot hold stage {stage.number} for resume ({exc})"
                    ) from exc
                # Hand forward what a later run would read back, so a
                # renderer defect fails on the next stage.
                loaded.append(replace(_staged(stage, stage.parse(text)), text=text))
                stage_texts[stage.number] = text
                _emit_roadmap_status(status_callback, slug=slug, stage=stage, fact="wrote")
                if run_logger is not None:
                    run_logger.roadmap_stage_written(
                        phase=phase,
                        stage=stage.number,
                        artifact_path=_brief_reference(
                            resume_dir_path(repo_root, slug) / f"stage-{stage.number}.md",
                            repo_root=repo_root,
                        ),
                        artifact_digest=digest_decoded_text(text),
                        replaced=False,
                        draft_seed_count=0,
                    )
                    run_logger.phase_end(phase, elapsed_ms, "ok")

        if result is None:
            artifacts: tuple[Path, ...] = ()
            # Only the full version inventory forms a root version; an injected
            # partial table (a programmatic seam, never the CLI) completes
            # holding its stages and publishes nothing.
            if tuple(stage.artifact_key for stage in ordered) == VERSION_ARTIFACT_KEYS:
                version_id = _publish_root_version(
                    slug=slug,
                    plans_dir=plans_dir,
                    writer_token=writer_token,
                    brief_bytes=brief_bytes,
                    stages=ordered,
                    stage_texts=stage_texts,
                )
                # Only after the head committed: a failed publish keeps the held stages.
                # A failed cleanup must not report the published roadmap as failed;
                # the next run deletes a stale resume directory beside a head.
                _delete_resume_or_warn(repo_root, slug, outcome="published")
                artifacts = tuple(
                    stored_artifact_path(plans_dir, slug, version_id, stage.artifact_key)
                    for stage in ordered
                )
            result = RoadmapResult(
                outcome=OUTCOME_COMPLETED,
                artifacts=artifacts,
                stages_run=tuple(stages_run),
                pending_decisions=sum(
                    _pending_decision_count(entry.artifact) for entry in loaded
                ),
                written_stages=tuple(stage.number for stage in ordered) if artifacts else (),
            )

        lifecycle.complete(
            outcome=result.outcome,
            rc=0 if is_successful_roadmap_outcome(result.outcome) else 1,
        )
        return result


# --------------------------------------------------------------------------
# Apply-only seed promotion
# --------------------------------------------------------------------------

APPLY_OUTCOME_APPLIED = "applied"
APPLY_OUTCOME_RECOMMENDED = "recommended"
APPLY_OUTCOME_REFUSED = "refused"

ACCEPT_OUTCOME_ACCEPTED = "accepted"
ACCEPT_OUTCOME_REFUSED = "refused"

APPLY_OUTCOMES: tuple[str, ...] = (
    APPLY_OUTCOME_APPLIED,
    APPLY_OUTCOME_RECOMMENDED,
    APPLY_OUTCOME_REFUSED,
)


@dataclass(frozen=True)
class RoadmapApplyResult:
    """What one apply-only seed promotion did. Facts only — no exit code."""

    outcome: str
    targets: tuple[tuple[str, Path, Path], ...] = ()
    promotions: tuple[tuple[str, Path, Path], ...] = ()
    collisions: tuple[Path, ...] = ()
    refused_drafts: tuple[DraftSeedClassification, ...] = ()
    bijection_error: str | None = None
    # Already-published seeds left untouched, as ``(plan_id, plan-seeds/dest)``.
    skipped: tuple[tuple[str, Path], ...] = ()
    # Skipped seeds whose draft is no longer current: warned, never refused, so
    # one out-of-date published copy cannot block promoting the new seeds.
    stale_published: tuple[DraftSeedClassification, ...] = ()


@dataclass(frozen=True)
class RoadmapSeedAcceptResult:
    """What accepting one directly edited roadmap draft did. Facts only."""

    outcome: str
    plan_id: str
    target: Path | None = None
    promoted_target: Path | None = None
    state: str | None = None
    detail: str | None = None
    violations: tuple[Violation, ...] = ()


def ordering_plans_bijection_error(artifact: PlansArtifact) -> str | None:
    """Fail-closed preflight: ``ordering`` and ``plans`` must name the same set."""
    plan_ids = {plan.id for plan in artifact.plans}
    ordering_ids = [entry.plan_id for entry in artifact.ordering]
    if len(ordering_ids) != len(set(ordering_ids)):
        duplicates = sorted(
            plan_id for plan_id in set(ordering_ids) if ordering_ids.count(plan_id) > 1
        )
        return f"plan id '{duplicates[0]}' appears more than once in {PLANS_FILENAME} 'ordering'"
    missing_from_ordering = sorted(plan_ids - set(ordering_ids))
    if missing_from_ordering:
        return (
            f"plan id '{missing_from_ordering[0]}' is declared in "
            f"{PLANS_FILENAME} 'plans' but absent from 'ordering'"
        )
    undefined_in_plans = sorted(set(ordering_ids) - plan_ids)
    if undefined_in_plans:
        return (
            f"ordering entry '{undefined_in_plans[0]}' names no plan row in "
            f"{PLANS_FILENAME} 'plans'"
        )
    return None


def ordered_plan_seed_targets(
    plans_dir: Path,
    slug: str,
    artifact: PlansArtifact,
    *,
    repo_root: Path,
) -> tuple[tuple[str, Path, Path], ...]:
    """Each ordered plan row as ``(plan_id, draft_source, plan-seeds/dest)``."""
    plan_by_id = {plan.id: plan for plan in artifact.plans}
    plan_seeds_dir = Path(repo_root) / "plan-seeds"
    targets: list[tuple[str, Path, Path]] = []
    for entry in artifact.ordering:
        plan = plan_by_id[entry.plan_id]
        source = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
        dest = resolve_plan_seed_dest(plan_seeds_dir, plan.id)
        targets.append((plan.id, source, dest))
    return tuple(targets)


def _promoted_seed_body(text: str, *, marker: str | None = None) -> str:
    """Validate draft provenance frontmatter and return prose-only body bytes.

    The marker is an HTML comment rather than user-facing seed prose.  It
    survives ``create``'s archive move and lets a later create invocation find
    the originating roadmap's invalidation state.
    """
    parse_draft_seed_provenance(text)
    from plan_tool.roadmap_artifacts import _parse_frontmatter

    _frontmatter, body = _parse_frontmatter(text, artifact="draft seed")
    if marker is None:
        return body
    return f"{body.rstrip()}\n\n{marker}\n"


def _register_roadmap_seed_promotions(
    artifact: PlansArtifact,
    *,
    plans_dir: Path,
    slug: str,
    source_text_by_plan_id: Mapping[str, str],
) -> None:
    """Record the admitted draft snapshots that gained ``plan-seeds/`` copies.

    Iterates ``source_text_by_plan_id`` — the plans actually promoted — not
    ``artifact.plans``: a plan row added to the roadmap during the apply
    confirm wait has no promoted snapshot and must not be recorded.
    """
    state = _load_roadmap_seed_state(plans_dir=plans_dir, slug=slug)
    entries = state["seeds"]
    plan_by_id = {row.id: row for row in artifact.plans}
    for plan_id, source_text in source_text_by_plan_id.items():
        old = entries.get(plan_id, {})
        entries[plan_id] = {
            "draft_seed_path": plan_by_id[plan_id].draft_seed_path,
            "status": old.get("status", "current"),
            "digest": digest_text(source_text),
            "published": True,
        }
    _write_roadmap_seed_state(state, plans_dir=plans_dir, slug=slug)


def _confirm_apply_seeds(
    prompt_fn: Optional[Callable[[str], str]],
    *,
    slug: str,
    yes: bool,
) -> bool:
    """Interactive apply confirm — mirrors :func:`plan_tool.scope_out._confirm_scope_out`."""
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            f"  roadmap apply for {slug} needs confirmation; re-run with -y to promote unattended.",
            file=sys.stderr,
        )
        return False
    confirm_fn = prompt_fn if prompt_fn is not None else input
    try:
        answer = (
            confirm_fn(f"Promote draft seeds for {slug} to plan-seeds/? [y/N]: ").strip().lower()
        )
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — plan-seeds/ left unchanged.", file=sys.stderr)
        return False
    return answer in ("y", "yes")


def _seed_recorded_published(entries: Mapping[str, Any], plan_id: str) -> bool:
    """The one publication test: the seed state records it. An existing file
    alone is not proof, since it may be hand-written or another roadmap's."""
    return bool(entries.get(plan_id, {}).get("published", False))


def _split_published_apply_targets(
    targets: tuple[tuple[str, Path, Path], ...],
    *,
    plans_dir: Path,
    slug: str,
) -> tuple[tuple[tuple[str, Path, Path], ...], tuple[tuple[str, Path], ...]]:
    """Split apply targets into unpublished ones and already-published skips.

    A seed is published when the seed state records it; promotion records it
    before ``create`` can archive the copy. An existing destination alone is
    not proof: an unpublished seed whose destination exists stays a target and
    refuses as a collision, so ``--apply`` never overwrites a file it did not
    write. Deliberately not an archive-filename check, which matches another
    roadmap's or a hand-written seed of the same name.
    """
    entries = _load_roadmap_seed_state(plans_dir=plans_dir, slug=slug)["seeds"]
    remaining: list[tuple[str, Path, Path]] = []
    skipped: list[tuple[str, Path]] = []
    for plan_id, source, dest in targets:
        if _seed_recorded_published(entries, plan_id):
            skipped.append((plan_id, dest))
        else:
            remaining.append((plan_id, source, dest))
    return tuple(remaining), tuple(skipped)


def _refused_apply_drafts(
    targets: tuple[tuple[str, Path, Path], ...],
    classifications: Mapping[str, DraftSeedClassification],
) -> tuple[DraftSeedClassification, ...]:
    """Return non-current targets in ordering sequence.

    A plan row removed after confirmation has no fresh classification, so it
    refuses without changing the already-confirmed target set.
    """
    refused: list[DraftSeedClassification] = []
    for plan_id, _source, _dest in targets:
        classification = classifications.get(plan_id)
        if classification is None:
            refused.append(
                DraftSeedClassification(
                    plan_id=plan_id,
                    state=DRAFT_SEED_STATE_MISSING,
                    detail="plan row is no longer present in 04-roadmap.md",
                )
            )
        elif classification.state != DRAFT_SEED_STATE_CURRENT:
            refused.append(classification)
    return tuple(refused)


def _refused_draft_state_counts(
    refused_drafts: Sequence[DraftSeedClassification],
) -> dict[str, int]:
    """Count apply refusals in the classifier's state vocabulary."""
    return {
        state: sum(draft.state == state for draft in refused_drafts)
        for state in (
            DRAFT_SEED_STATE_MISSING,
            DRAFT_SEED_STATE_MALFORMED,
            DRAFT_SEED_STATE_STALE,
            DRAFT_SEED_STATE_PATH_ESCAPING,
            DRAFT_SEED_STATE_DUPLICATE,
            DRAFT_SEED_STATE_DIGEST_MISMATCHED,
        )
    }


def accept_roadmap_seed(
    slug: str,
    plan_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
) -> RoadmapSeedAcceptResult:
    """Accept one directly edited draft while owning its roadmap baseline."""
    with _roadmap_writer_owner(plans_dir, slug) as writer_token:
        _require_roadmap_writer_or_raise(
            writer_token, plans_dir=plans_dir, slug=slug
        )
        return _accept_roadmap_seed(
            slug,
            plan_id,
            repo_root=repo_root,
            plans_dir=plans_dir,
        )


def _accept_roadmap_seed(
    slug: str,
    plan_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
) -> RoadmapSeedAcceptResult:
    """Record one validated, directly edited digest-mismatched draft as current."""
    repo_root = Path(repo_root)
    plans_dir = Path(plans_dir)
    try:
        root = roadmap_dir(plans_dir, slug)
    except ValueError as exc:
        raise RoadmapError(str(exc)) from exc

    artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=slug)
    plan = next((row for row in artifact.plans if row.id == plan_id), None)
    if plan is None:
        return RoadmapSeedAcceptResult(
            outcome=ACCEPT_OUTCOME_REFUSED,
            plan_id=plan_id,
        )

    try:
        classification = classify_draft_seeds(artifact, plans_dir=plans_dir, slug=slug).get(plan_id)
    except RoadmapSeedStateError as exc:
        raise RoadmapError(str(exc)) from exc
    if classification is None or classification.state != DRAFT_SEED_STATE_DIGEST_MISMATCHED:
        return RoadmapSeedAcceptResult(
            outcome=ACCEPT_OUTCOME_REFUSED,
            plan_id=plan_id,
            state=None if classification is None else classification.state,
            detail=None if classification is None else classification.detail,
        )

    source = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RoadmapError(
            f"roadmap seed '{plan_id}' draft at {source} became unreadable "
            f"between classification and read: {exc}"
        ) from exc
    violations = tuple(validate_draft_seed_content(text, plan=plan))
    if violations:
        return RoadmapSeedAcceptResult(
            outcome=ACCEPT_OUTCOME_REFUSED,
            plan_id=plan_id,
            target=source,
            violations=violations,
        )

    state = _load_roadmap_seed_state(plans_dir=plans_dir, slug=slug)
    entries = state["seeds"]
    published = _seed_recorded_published(entries, plan_id)

    # Copy first, sidecar second (as materialize does): a failed copy write
    # leaves the draft digest-mismatched, so --accept-seed can be re-run.
    promoted = resolve_plan_seed_dest(repo_root / "plan-seeds", plan_id)
    if published:
        try:
            atomic_write_text(
                promoted,
                _promoted_seed_body(
                    text,
                    marker=render_seed_state_marker(
                        state_path=seed_state_path(root),
                        repo_root=repo_root,
                        roadmap_slug=slug,
                        plan_id=plan_id,
                    ),
                ),
            )
        except OSError as exc:
            raise RoadmapError(
                f"roadmap seed '{plan_id}': could not write the promoted copy "
                f"{promoted}: {exc}. Nothing was recorded; re-run "
                f"--accept-seed {plan_id} once the path is writable."
            ) from exc
        promoted_target: Path | None = promoted
    else:
        promoted_target = None

    entries[plan_id] = {
        "draft_seed_path": plan.draft_seed_path,
        "status": "current",
        "digest": digest_text(text),
        "published": published,
    }
    _write_roadmap_seed_state(state, plans_dir=plans_dir, slug=slug)

    return RoadmapSeedAcceptResult(
        outcome=ACCEPT_OUTCOME_ACCEPTED,
        plan_id=plan_id,
        target=source,
        promoted_target=promoted_target,
    )


def apply_roadmap_seeds(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    allow_apply: bool,
    yes: bool = False,
    prompt_fn: Optional[Callable[[str], str]] = None,
    run_logger: Optional[RunLoggerLike] = None,
) -> RoadmapApplyResult:
    """Promote roadmap seeds while owning their mutable roadmap baseline."""
    _reject_unmatched_operator_draft_fences(slug, plans_dir=plans_dir)
    with _roadmap_writer_owner(plans_dir, slug) as writer_token:
        _require_roadmap_writer_or_raise(
            writer_token, plans_dir=plans_dir, slug=slug
        )
        return _apply_roadmap_seeds_owner(
            slug,
            repo_root=repo_root,
            plans_dir=plans_dir,
            allow_apply=allow_apply,
            yes=yes,
            prompt_fn=prompt_fn,
            run_logger=run_logger,
            writer_token=writer_token,
        )


def _reject_unmatched_operator_draft_fences(slug: str, *, plans_dir: Path) -> None:
    """Reject readable operator drafts before a command lifecycle starts."""
    artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=slug)
    for plan in artifact.plans:
        source = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violation = next(
            (
                item
                for item in validate_draft_seed_content(text, plan=plan)
                if item.kind == VIOLATION_DRAFT_SEED_UNMATCHED_FENCE
            ),
            None,
        )
        if violation is not None:
            raise RoadmapError(violation.message)


def _apply_roadmap_seeds_owner(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    allow_apply: bool,
    yes: bool = False,
    prompt_fn: Optional[Callable[[str], str]] = None,
    run_logger: Optional[RunLoggerLike] = None,
    writer_token: RoadmapWriterToken,
) -> RoadmapApplyResult:
    """Promote slug-directory draft seeds into ``plan-seeds/`` after opt-in confirm.

    Reads the accepted version's roadmap artifact; never invokes the roadmap backend or stage
    loop. Seeds the seed state records as published are skipped, with a warning
    when their draft is no longer current. Refuse-by-default for the rest: a
    non-current draft, an existing destination, or an ordering-bijection
    failure blocks promotion with no writes.
    On confirm, stages every promoted body then commits via ``os.link``, which
    refuses a destination that appeared after preflight instead of clobbering
    it; a failed or refused commit rolls back what landed so the tree stays
    unchanged.
    """
    repo_root = Path(repo_root)
    plans_dir = Path(plans_dir)
    with _roadmap_command_lifecycle(
        repo_root=repo_root,
        plans_dir=plans_dir,
        slug=slug,
        run_logger=run_logger,
        flags={"mode": "apply", "yes": yes, "allow_apply": allow_apply},
    ) as lifecycle:
        run_logger = lifecycle.run_logger
        result = _apply_roadmap_seeds(
            slug,
            repo_root=repo_root,
            plans_dir=plans_dir,
            allow_apply=allow_apply,
            yes=yes,
            prompt_fn=prompt_fn,
            writer_token=writer_token,
        )
        if run_logger is not None:
            refusal_counts = _refused_draft_state_counts(result.refused_drafts)
            run_logger.roadmap_seed_apply_result(
                outcome=result.outcome,
                target_count=len(result.targets),
                promotion_count=len(result.promotions),
                collision_count=len(result.collisions),
                missing_draft_count=refusal_counts[DRAFT_SEED_STATE_MISSING],
                malformed_draft_count=refusal_counts[DRAFT_SEED_STATE_MALFORMED],
                stale_draft_count=refusal_counts[DRAFT_SEED_STATE_STALE],
                path_escaping_draft_count=refusal_counts[DRAFT_SEED_STATE_PATH_ESCAPING],
                duplicate_draft_count=refusal_counts[DRAFT_SEED_STATE_DUPLICATE],
                digest_mismatched_draft_count=refusal_counts[DRAFT_SEED_STATE_DIGEST_MISMATCHED],
            )
        lifecycle.complete(
            outcome=result.outcome,
            rc=2 if result.outcome == APPLY_OUTCOME_REFUSED else 0,
        )
        return result


def _apply_roadmap_seeds(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    allow_apply: bool,
    yes: bool,
    prompt_fn: Optional[Callable[[str], str]],
    writer_token: RoadmapWriterToken,
) -> RoadmapApplyResult:
    """The apply-only seed promotion body, under its caller's run-log scope."""
    try:
        require_roadmap_writer_token(writer_token, plans_dir=plans_dir, slug=slug)
    except RoadmapWriterGuardError as exc:
        raise RoadmapError(str(exc)) from exc
    try:
        artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=slug)
    except (RoadmapArtifactError, RoadmapSeedStateError) as exc:
        raise RoadmapError(str(exc)) from exc

    bijection_error = ordering_plans_bijection_error(artifact)
    if bijection_error is not None:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            bijection_error=bijection_error,
        )

    ordered_targets = ordered_plan_seed_targets(
        plans_dir, slug, artifact, repo_root=repo_root
    )
    targets, skipped = _split_published_apply_targets(
        ordered_targets, plans_dir=plans_dir, slug=slug
    )

    collisions: list[Path] = []
    try:
        classifications = classify_draft_seeds(artifact, plans_dir=plans_dir, slug=slug)
    except RoadmapSeedStateError as exc:
        raise RoadmapError(str(exc)) from exc
    refused_drafts = _refused_apply_drafts(targets, classifications)
    skipped_ids = {plan_id for plan_id, _dest in skipped}
    stale_published = tuple(
        classification
        for classification in _refused_apply_drafts(ordered_targets, classifications)
        if classification.plan_id in skipped_ids
    )
    for _plan_id, _source, dest in targets:
        if dest.exists():
            collisions.append(dest)

    if refused_drafts or collisions:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
            collisions=tuple(collisions),
            refused_drafts=refused_drafts,
        )

    if not allow_apply or not targets:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_RECOMMENDED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
        )

    if not _confirm_apply_seeds(prompt_fn, slug=slug, yes=yes):
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_RECOMMENDED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
        )

    try:
        fresh_artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=slug)
    except (RoadmapArtifactError, RoadmapSeedStateError) as exc:
        raise RoadmapError(str(exc)) from exc
    try:
        classifications = classify_draft_seeds(fresh_artifact, plans_dir=plans_dir, slug=slug)
    except RoadmapSeedStateError as exc:
        raise RoadmapError(str(exc)) from exc
    refused_drafts = _refused_apply_drafts(targets, classifications)
    stale_published = tuple(
        classification
        for classification in _refused_apply_drafts(ordered_targets, classifications)
        if classification.plan_id in skipped_ids
    )
    if refused_drafts:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
            refused_drafts=refused_drafts,
        )

    # Every plan_id surviving the refusal check above has a ``current``
    # classification against ``fresh_artifact``, so it also has a row there —
    # rebuild each target's source from that fresh row rather than the
    # pre-confirm ``targets``, or a draft_seed_path change made during the
    # confirm wait would revalidate against the new file but still commit the
    # old one.
    fresh_plan_by_id = {plan.id: plan for plan in fresh_artifact.plans}
    targets = tuple(
        (
            plan_id,
            resolve_draft_seed_path(plans_dir, slug, fresh_plan_by_id[plan_id].draft_seed_path),
            dest,
        )
        for plan_id, _stale_source, dest in targets
    )

    admitted_source_texts: dict[str, str] = {}
    post_classification_refusals: list[DraftSeedClassification] = []
    for plan_id, source, _dest in targets:
        source_text = source.read_text(encoding="utf-8")
        violations = validate_draft_seed_content(
            source_text, plan=fresh_plan_by_id[plan_id]
        )
        if violations:
            post_classification_refusals.append(
                DraftSeedClassification(
                    plan_id=plan_id,
                    state=DRAFT_SEED_STATE_MALFORMED,
                    detail="\n".join(violation.message for violation in violations),
                )
            )
            continue
        admitted_source_texts[plan_id] = source_text

    if post_classification_refusals:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
            refused_drafts=tuple(post_classification_refusals),
        )

    plan_seeds_dir = repo_root / "plan-seeds"
    plan_seeds_dir.mkdir(parents=True, exist_ok=True)

    # Two-phase commit: stage every body to a sibling tempfile, then link it
    # into place. ``os.link`` and not ``os.replace`` because the confirm above
    # holds the preflight's check-to-use window open for as long as the
    # operator takes to answer, and replace would silently clobber a
    # destination created inside it — the one thing refuse-by-default exists
    # to prevent. Everything committed is therefore a file this call created,
    # so rolling back can never delete someone else's.
    staged: list[tuple[str, Path, Path, Path]] = []
    late_collision: Optional[Path] = None
    try:
        for plan_id, source, dest in targets:
            body = _promoted_seed_body(
                admitted_source_texts[plan_id],
                marker=render_seed_state_marker(
                    state_path=seed_state_path(roadmap_dir(plans_dir, slug)),
                    repo_root=repo_root,
                    roadmap_slug=slug,
                    plan_id=plan_id,
                ),
            )
            tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
            tmp.write_text(body, encoding="utf-8")
            staged.append((plan_id, source, dest, tmp))

        promotions: list[tuple[str, Path, Path]] = []
        committed: list[Path] = []
        try:
            for plan_id, source, dest, tmp in staged:
                try:
                    os.link(tmp, dest)
                except FileExistsError:
                    late_collision = dest
                    break
                committed.append(dest)
                promotions.append((plan_id, source, dest))
        except OSError:
            for path in committed:
                path.unlink(missing_ok=True)
            raise
        if late_collision is not None:
            for path in committed:
                path.unlink(missing_ok=True)
    finally:
        for _plan_id, _source, _dest, tmp in staged:
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()

    if late_collision is not None:
        return RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            skipped=skipped,
            stale_published=stale_published,
            targets=targets,
            collisions=(late_collision,),
        )

    _register_roadmap_seed_promotions(
        fresh_artifact,
        plans_dir=plans_dir,
        slug=slug,
        source_text_by_plan_id=admitted_source_texts,
    )

    return RoadmapApplyResult(
        outcome=APPLY_OUTCOME_APPLIED,
        skipped=skipped,
        stale_published=stale_published,
        targets=targets,
        promotions=tuple(promotions),
    )


# --------------------------------------------------------------------------
# Explicit seed refresh
# --------------------------------------------------------------------------

SEED_REFRESH_OUTCOME_APPLIED = "refreshed"
SEED_REFRESH_OUTCOME_EXHAUSTED = "refresh-exhausted"
SEED_REFRESH_OUTCOME_PARTIAL = "refresh-partial"


@dataclass(frozen=True)
class RoadmapSeedRefreshChange:
    """One seed file compared during an explicit refresh."""

    plan_id: str
    target: Path
    previous: Path | None
    action: str  # ``updated``, ``recreated``, ``created``, or ``unchanged``.
    diff: str


@dataclass(frozen=True)
class RoadmapSeedRefreshFailure:
    """One plan seed that remained invalidated after refresh retries."""

    plan_id: str
    failure_kind: str
    failure_detail: str | None = None
    violations: tuple[Violation, ...] = ()


@dataclass(frozen=True)
class RoadmapSeedRefreshResult:
    """The outcome and durable report of one explicit seed refresh."""

    outcome: str
    changes: tuple[RoadmapSeedRefreshChange, ...] = ()
    failures: tuple[RoadmapSeedRefreshFailure, ...] = ()
    report_path: Path | None = None


SEED_MATERIALIZE_OUTCOME_APPLIED = "materialized"
SEED_MATERIALIZE_OUTCOME_EXHAUSTED = "materialize-exhausted"


@dataclass(frozen=True)
class RoadmapSeedMaterializeResult:
    """What one independently generated draft seed did."""

    outcome: str
    plan_id: str
    draft_seed_path: Path | None = None
    failure_kind: str | None = None
    failure_rc: int | None = None
    failure_detail: str | None = None
    violations: tuple[Violation, ...] = ()


def _render_seed_materialize_prompt(
    *, slug: str, plan_id: str, loaded: Sequence[_LoadedArtifact]
) -> str:
    """Render the standalone prompt for one accepted roadmap plan row."""
    template_path = prompts_dir() / "roadmap-seed.md"
    if not template_path.is_file():
        raise RoadmapError(
            f"no prompt template for roadmap seed materialization at {template_path}"
        )

    def unreadable_prompt_input(exc: OSError | UnicodeDecodeError) -> RoadmapEnvironmentalError:
        return RoadmapEnvironmentalError(
            f"roadmap seed materialization prompt input is not readable ({exc})"
        )

    variables = {"slug": slug, "plan_id": plan_id}
    variables.update({f"{item.stage.artifact_key}_artifact": item.text for item in loaded})
    template_text = read_roadmap_text(
        template_path, error_for_read_failure=unreadable_prompt_input
    )
    return Template(template_text).safe_substitute(variables)


def materialize_plan_seed(
    slug: str,
    plan_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
    writer_token: RoadmapWriterToken | None = None,
    materialization_observer: _MaterializationObserver | None = None,
) -> RoadmapSeedMaterializeResult:
    """Generate one draft seed while owning or reusing its roadmap guard."""
    if writer_token is None:
        with _roadmap_writer_owner(plans_dir, slug) as owned_token:
            _require_roadmap_writer_or_raise(
                owned_token, plans_dir=plans_dir, slug=slug
            )
            return _materialize_plan_seed(
                slug,
                plan_id,
                repo_root=repo_root,
                plans_dir=plans_dir,
                invoker=invoker,
                max_attempts=max_attempts,
                materialization_observer=materialization_observer,
            )
    _require_roadmap_writer_or_raise(
        writer_token, plans_dir=plans_dir, slug=slug
    )
    return _materialize_plan_seed(
        slug,
        plan_id,
        repo_root=repo_root,
        plans_dir=plans_dir,
        invoker=invoker,
        max_attempts=max_attempts,
        materialization_observer=materialization_observer,
    )


_STACK_HEADING = "## Stack"
_OPEN_PRODUCT_TEXT = "product left open by the accepted roadmap"
_TECHNOLOGY_STACK_HEADING = "### Technology stack"
_STACK_NOT_RECORDED_TEXT = "- (none) The accepted roadmap version does not record a technology stack."
_STACK_EMPTY_TEXT = "- (none) The accepted roadmap records a technology stack with no concerns."
_STACK_OPEN_TEXT = "open — not decided by the accepted roadmap"


def _cell(value: Any) -> str:
    """One physical line of text: embedded newlines or runs of space collapse."""
    return " ".join(str(value).split())


def _product_text(product: Any) -> str:
    """A row's product on one line, or the explicit open wording when blank."""
    text = _cell(product) if product is not None else ""
    return text or _OPEN_PRODUCT_TEXT


def _render_stack_section(
    *,
    version_id: str,
    hosting: Sequence[Any],
    stores: Sequence[Any],
    components: Sequence[Any],
    stack: Optional[Sequence[Any]],
    plan: PlanRow,
) -> str:
    """The tool-owned ``## Stack`` section: a pure function of accepted rows.

    ``stack`` is ``None`` when the version predates the collection and ``()``
    when it is recorded and empty; the two render as different lines.

    A dangling ``store_ids`` entry is a component-gate finding, so it is
    skipped here rather than raised.
    """
    owned_component_ids = set(plan.component_ids)
    wanted_store_ids = {
        store_id
        for component in components
        if component.id in owned_component_ids
        for store_id in component.store_ids
    }
    lines = [
        _STACK_HEADING,
        "",
        f"Settled by the accepted roadmap (version `{version_id}`); "
        "treat these rows as constraints, not options, except a technology stack "
        "concern marked open, which the accepted roadmap has not decided.",
        "",
        "### Hosting",
        "",
    ]
    if hosting:
        for row in hosting:
            lines.append(
                f"- `{_cell(row.id)}` — facet: {_cell(row.facet)}; value: {_cell(row.value)}; "
                f"product: {_product_text(row.product)}"
            )
    else:
        lines.append("- (none) The accepted roadmap lists no hosting rows.")
    lines += ["", "### Stores", ""]
    plan_stores = [store for store in stores if store.id in wanted_store_ids]
    if plan_stores:
        for row in plan_stores:
            lines.append(
                f"- `{_cell(row.id)}` — category: {_cell(row.category)}; "
                f"sharing: {_cell(row.sharing)}; product: {_product_text(row.product)}"
            )
    else:
        lines.append("- (none) This plan row's components name no store, so none is listed here.")
    lines += ["", _TECHNOLOGY_STACK_HEADING, ""]
    if stack is None:
        lines.append(_STACK_NOT_RECORDED_TEXT)
    elif not stack:
        lines.append(_STACK_EMPTY_TEXT)
    else:
        for row in stack:
            decision = _STACK_OPEN_TEXT if row.open else f"choice: {_cell(row.choice or 'no choice')}"
            lines.append(f"- `{_cell(row.id)}` — concern: {_cell(row.concern)}; {decision}")
    return "\n".join(lines) + "\n"


def _replace_stack_section(text: str, section: str) -> str:
    """Drop every real ``## Stack`` H2 section, then insert ``section``.

    Headings and fences are recognized by ``scope_fence.h2_section_spans``, the
    rules ``create`` reads a seed with, so no model-authored variant survives
    to be read in place of the tool's section. The tool's section goes before
    ``## References``, or at the end when there is none. The leading YAML
    frontmatter is never scanned or rewritten: a column-0 ``##`` comment or a
    fence-looking line inside it is not a section, which is the rule the
    draft-seed validator reads with.
    """
    body = _strip_frontmatter(text)
    prefix = text[: len(text) - len(body)]
    for start, end in reversed(h2_section_spans(body, "stack")):
        body = body[:start] + body[end:]
    references = h2_section_spans(body, "references")
    if not references:
        return prefix + body.rstrip("\n") + "\n\n" + section
    insert_at = references[0][0]
    return prefix + body[:insert_at] + section + "\n" + body[insert_at:]


def _materialize_plan_seed(
    slug: str,
    plan_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
    materialization_observer: _MaterializationObserver | None = None,
) -> RoadmapSeedMaterializeResult:
    """Generate, validate, and record one plan row's draft seed.

    The sidecar commits last: a stopped write therefore remains detectable as a
    missing or digest-mismatched draft rather than claiming a stale copy is current.
    """
    repo_root = Path(repo_root)
    plans_dir = Path(plans_dir)
    try:
        roadmap_dir(plans_dir, slug)
    except ValueError as exc:
        raise RoadmapError(str(exc)) from exc

    loaded = load_accepted_roadmap_artifacts(plans_dir=plans_dir, slug=slug)
    artifact = loaded[-1].artifact
    if not isinstance(artifact, PlansArtifact):  # Defensive against a custom stage table.
        raise RoadmapError("roadmap seed materialization requires a plans artifact at stage 4")
    plan = next((row for row in artifact.plans if row.id == plan_id), None)
    if plan is None:
        raise RoadmapError(f"roadmap '{slug}' has no plan id '{plan_id}' in {PLANS_FILENAME}")

    # The version id comes from the same read as the artifacts (the member
    # directory is named for it), so the stack can never cite another version.
    stack_section = _render_stack_section(
        version_id=loaded[0].path.parent.name,
        hosting=getattr(loaded[1].artifact, "hosting", ()),
        stores=getattr(loaded[2].artifact, "stores", ()),
        components=getattr(loaded[2].artifact, "components", ()),
        stack=getattr(loaded[1].artifact, "stack", None),
        plan=plan,
    )

    base_prompt = _render_seed_materialize_prompt(slug=slug, plan_id=plan_id, loaded=loaded)
    corrections: tuple[str, ...] = ()
    failure_kind: str | None = None
    failure_rc: int | None = None
    failure_detail: str | None = None
    violations: tuple[Violation, ...] = ()

    for seed_attempt in range(1, max_attempts + 1):
        prompt = base_prompt
        if corrections:
            prompt += _corrections_block(corrections)
        if materialization_observer is not None:
            materialization_observer.begin_seed_attempt(
                seed_attempt=seed_attempt,
                prompt_bytes=len(prompt.encode("utf-8")),
                prompt_sha256=hash_prompt(prompt),
            )
            shell_scope = materialization_observer.bind_shell_observer()
        else:
            shell_scope = contextlib.nullcontext()
        with shell_scope:
            rc, reply = invoker(prompt)
        if rc != 0 or not reply.strip():
            failure_kind = FAILURE_INVOKE
            failure_rc = rc
            failure_detail = _reply_head(reply)
            violations = ()
            if materialization_observer is not None:
                materialization_observer.candidate_failed(
                    failure_kind=failure_kind,
                    failure_rc=failure_rc,
                    violation_count=0,
                    reply_present=bool(reply.strip()),
                    failure_detail_present=bool(failure_detail),
                )
            corrections = (
                "the previous attempt produced no usable draft seed "
                f"(exit code {rc}) — reply with the complete seed text and nothing else",
            )
            continue

        lifted = _lift_artifact_text(reply, strip_unpaired_trailing_fence=False)
        if lifted is None:
            failure_kind = FAILURE_PARSE
            failure_rc = None
            failure_detail = _reply_head(reply)
            violations = ()
            if materialization_observer is not None:
                materialization_observer.candidate_failed(
                    failure_kind=failure_kind,
                    failure_rc=failure_rc,
                    violation_count=0,
                    reply_present=True,
                    failure_detail_present=True,
                )
            corrections = (
                f"the previous response carried no draft seed: it must open on a "
                f"'{_FRONTMATTER_FENCE}' provenance frontmatter fence and continue "
                "with the seed body",
            )
            continue

        lifted = _replace_stack_section(lifted, stack_section)
        candidate_violations = tuple(validate_draft_seed_content(lifted, plan=plan))
        if candidate_violations:
            failure_kind = FAILURE_GATES
            failure_rc = None
            failure_detail = None
            violations = candidate_violations
            if materialization_observer is not None:
                materialization_observer.candidate_failed(
                    failure_kind=failure_kind,
                    failure_rc=failure_rc,
                    violation_count=len(candidate_violations),
                    reply_present=True,
                    failure_detail_present=False,
                )
            corrections = tuple(item.message for item in candidate_violations)
            continue

        target = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
        atomic_write_text(target, lifted)

        state = _load_roadmap_seed_state(plans_dir=plans_dir, slug=slug)
        entries = state["seeds"]
        promoted = resolve_plan_seed_dest(repo_root / "plan-seeds", plan.id)
        published = _seed_recorded_published(entries, plan.id)
        if published:
            atomic_write_text(
                promoted,
                _promoted_seed_body(
                    lifted,
                    marker=render_seed_state_marker(
                        state_path=seed_state_path(roadmap_dir(plans_dir, slug)),
                        repo_root=repo_root,
                        roadmap_slug=slug,
                        plan_id=plan.id,
                    ),
                ),
            )

        entries[plan.id] = {
            "draft_seed_path": plan.draft_seed_path,
            "status": "current",
            "digest": digest_text(lifted),
            "published": published,
        }
        _write_roadmap_seed_state(state, plans_dir=plans_dir, slug=slug)
        return RoadmapSeedMaterializeResult(
            outcome=SEED_MATERIALIZE_OUTCOME_APPLIED,
            plan_id=plan.id,
            draft_seed_path=target,
        )

    return RoadmapSeedMaterializeResult(
        outcome=SEED_MATERIALIZE_OUTCOME_EXHAUSTED,
        plan_id=plan.id,
        failure_kind=failure_kind,
        failure_rc=failure_rc,
        failure_detail=failure_detail,
        violations=violations,
    )


def _seed_refresh_diff(before: str, after: str, *, previous: Path | None, target: Path) -> str:
    """A compact, standard report diff for one regenerated seed."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(previous or target),
            tofile=str(target),
        )
    )


def _render_seed_refresh_report(
    slug: str,
    changes: Sequence[RoadmapSeedRefreshChange],
    failures: Sequence[RoadmapSeedRefreshFailure],
) -> str:
    """Persist the user-visible comparison whenever a seed is regenerated."""
    lines = [f"# Roadmap seed refresh: {slug}", ""]
    for change in changes:
        prior = str(change.previous) if change.previous is not None else "(no prior seed)"
        lines.extend(
            (
                f"## {change.plan_id} — {change.action}",
                "",
                f"Previous: `{prior}`",
                f"Current: `{change.target}`",
                "",
            )
        )
        if change.diff:
            lines.extend(("```diff", change.diff.rstrip(), "```", ""))
        else:
            lines.extend(("No content difference.", ""))
    for failure in failures:
        lines.extend(
            (
                f"## {failure.plan_id} — failed ({failure.failure_kind})",
                "",
            )
        )
        for violation in failure.violations:
            lines.append(f"- {violation.message}")
        if failure.failure_detail:
            lines.append(f"- Unusable reply: {failure.failure_detail}")
        if not failure.violations and not failure.failure_detail:
            lines.append("- No additional failure detail was recorded.")
        lines.append("")
    return "\n".join(lines)


def materialize_and_diff_one_plan(
    slug: str,
    row: PlanRow,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
    writer_token: RoadmapWriterToken | None = None,
    materialization_observer: _MaterializationObserver | None = None,
) -> tuple[tuple[RoadmapSeedRefreshChange, ...], RoadmapSeedRefreshFailure | None]:
    """Materialize one row while reusing its batch writer token when supplied."""
    if writer_token is None:
        with _roadmap_writer_owner(plans_dir, slug) as owned_token:
            _require_roadmap_writer_or_raise(
                owned_token, plans_dir=plans_dir, slug=slug
            )
            return _materialize_and_diff_one_plan(
                slug,
                row,
                repo_root=repo_root,
                plans_dir=plans_dir,
                invoker=invoker,
                max_attempts=max_attempts,
                writer_token=owned_token,
                materialization_observer=materialization_observer,
            )
    _require_roadmap_writer_or_raise(
        writer_token, plans_dir=plans_dir, slug=slug
    )
    return _materialize_and_diff_one_plan(
        slug,
        row,
        repo_root=repo_root,
        plans_dir=plans_dir,
        invoker=invoker,
        max_attempts=max_attempts,
        writer_token=writer_token,
        materialization_observer=materialization_observer,
    )


def _materialize_and_diff_one_plan(
    slug: str,
    row: PlanRow,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
    writer_token: RoadmapWriterToken,
    materialization_observer: _MaterializationObserver | None = None,
) -> tuple[tuple[RoadmapSeedRefreshChange, ...], RoadmapSeedRefreshFailure | None]:
    """Materialize one row and retain the refresh report's comparison shape."""
    repo_root = Path(repo_root)
    plans_dir = Path(plans_dir)
    draft_path = resolve_draft_seed_path(plans_dir, slug, row.draft_seed_path)
    promoted_path = resolve_plan_seed_dest(repo_root / "plan-seeds", row.id)
    entries = _load_roadmap_seed_state(plans_dir=plans_dir, slug=slug)["seeds"]
    # An unpublished seed's plan-seeds file is not the tool's: neither read nor
    # reported, since refresh will not rewrite it.
    targets = (
        (draft_path, promoted_path)
        if _seed_recorded_published(entries, row.id)
        else (draft_path,)
    )
    previous_by_target = {
        target: target if target.is_file() else latest_seed_archive(target) for target in targets
    }
    before_by_target = {
        target: previous.read_text(encoding="utf-8") if previous is not None else ""
        for target, previous in previous_by_target.items()
    }

    result = materialize_plan_seed(
        slug,
        row.id,
        repo_root=repo_root,
        plans_dir=plans_dir,
        invoker=invoker,
        max_attempts=max_attempts,
        writer_token=writer_token,
        materialization_observer=materialization_observer,
    )
    if result.outcome != SEED_MATERIALIZE_OUTCOME_APPLIED:
        return (), RoadmapSeedRefreshFailure(
            plan_id=row.id,
            failure_kind=result.failure_kind or "unknown",
            failure_detail=result.failure_detail,
            violations=result.violations,
        )

    changes: list[RoadmapSeedRefreshChange] = []
    for target in targets:
        if not target.exists():
            continue
        previous = previous_by_target[target]
        before = before_by_target[target]
        refreshed = target.read_text(encoding="utf-8")
        diff = _seed_refresh_diff(before, refreshed, previous=previous, target=target)
        if target == previous:
            action = "unchanged" if before == refreshed else "updated"
        elif previous is not None:
            action = "recreated"
        else:
            action = "created"
        changes.append(
            RoadmapSeedRefreshChange(
                plan_id=row.id,
                target=target,
                previous=previous,
                action=action,
                diff=diff,
            )
        )
    return tuple(changes), None


def write_seed_refresh_report(
    slug: str,
    changes: Sequence[RoadmapSeedRefreshChange],
    failures: Sequence[RoadmapSeedRefreshFailure] = (),
    *,
    plans_dir: Path,
) -> Path | None:
    """Write the shared refresh report only when one row produced a result."""
    if not changes and not failures:
        return None
    report_path = seed_refresh_report_path(roadmap_dir(plans_dir, slug))
    atomic_write_text(report_path, _render_seed_refresh_report(slug, changes, failures))
    return report_path


def _materialize_seed_rows(
    slug: str,
    rows: Sequence[PlanRow],
    *,
    repo_root: Path,
    plans_dir: Path,
    run_logger: RunLoggerLike,
    changes: list[RoadmapSeedRefreshChange],
    failures: list[RoadmapSeedRefreshFailure],
    invoker: StageInvoker | None = None,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
    writer_token: RoadmapWriterToken,
) -> None:
    """Materialize each row in order, phase-scoped on ``run_logger``.

    Shared by ``refresh_roadmap_seeds`` and the CLI's ``--materialize``
    handler — the two previously hand-rolled this loop independently and
    had already drifted (one gained a KeyboardInterrupt lifecycle fix the
    other lacked).

    Appends to the caller-owned ``changes``/``failures`` lists as each row
    completes, so a row that raises — ``RoadmapError``, ``RoadmapArtifactError``,
    ``KeyboardInterrupt``, or anything else — still leaves every prior row's
    result in those lists for the caller to report before deciding how to
    complete its own lifecycle and re-raising.

    Resets the writer's tracked termination reason once a batch of more than
    one row finishes, so a multi-row command's ``run_end`` never inherits a
    single row's own backend-termination reason as if it summarized the
    whole batch — see ``RunLogWriter.reset_termination_reason``.
    """
    extra: dict[str, Any] = {"invoker": invoker} if invoker is not None else {}
    for row in rows:
        phase = f"seed-materialize:{row.id}"
        phase_started_at = time.monotonic()
        phase_started = False
        phase_outcome = "error"
        run_logger.update_context(
            active_plan_id=row.id,
            seed_attempt=None,
            backend_attempt=None,
            backend_child_started=False,
        )
        try:
            run_logger.phase_start(phase)
            phase_started = True
            observer = _MaterializationObserver(run_logger, plan_id=row.id, phase=phase)
            row_changes, row_failure = materialize_and_diff_one_plan(
                slug,
                row,
                repo_root=repo_root,
                plans_dir=plans_dir,
                max_attempts=max_attempts,
                writer_token=writer_token,
                materialization_observer=observer,
                **extra,
            )
        except (RoadmapError, RoadmapArtifactError):
            phase_outcome = "preflight-refused" if not (changes or failures) else "row-refused"
            raise
        except KeyboardInterrupt:
            phase_outcome = "interrupted"
            raise
        except BaseException:
            # Exception text can include seed material, so preserve only
            # this static failure class in the row-level event.
            run_logger.attempt_failed(
                phase=phase,
                attempt=0,
                failure_kind="materialize-error",
            )
            raise
        else:
            phase_outcome = "exhausted" if row_failure is not None else "ok"
            if row_failure is not None:
                failures.append(row_failure)
            else:
                changes.extend(row_changes)
        finally:
            # Phase end retains its row attribution; the following snapshot
            # and every terminal record are inactive.
            run_logger.update_context(
                seed_attempt=None,
                backend_attempt=None,
                backend_child_started=False,
            )
            try:
                if phase_started:
                    run_logger.phase_end(
                        phase,
                        int((time.monotonic() - phase_started_at) * 1000),
                        phase_outcome,
                    )
            finally:
                run_logger.update_context(active_plan_id=None)

    if len(rows) > 1:
        reset = getattr(run_logger, "reset_termination_reason", None)
        if reset is not None:
            reset()


def refresh_roadmap_seeds(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker | None = None,
    max_stage_attempts: int = MAX_STAGE_ATTEMPTS,
) -> RoadmapSeedRefreshResult:
    """Refresh every roadmap-derived seed under one writer guard."""
    with _roadmap_writer_owner(plans_dir, slug) as writer_token:
        _require_roadmap_writer_or_raise(
            writer_token, plans_dir=plans_dir, slug=slug
        )
        return _refresh_roadmap_seeds(
            slug,
            repo_root=repo_root,
            plans_dir=plans_dir,
            invoker=invoker,
            max_stage_attempts=max_stage_attempts,
            writer_token=writer_token,
        )


def _refresh_roadmap_seeds(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_stage_attempts: int = MAX_STAGE_ATTEMPTS,
    writer_token: RoadmapWriterToken,
) -> RoadmapSeedRefreshResult:
    """Refresh every plan seed independently and report landed and failed rows."""
    repo_root = Path(repo_root)
    plans_dir = Path(plans_dir)

    context = {
        "roadmap_action": "refresh-seeds",
        "roadmap_slug": slug,
        "requested_plan_id": None,
        "active_plan_id": None,
        "seed_attempt": None,
        "backend_attempt": None,
        "backend_child_started": False,
    }
    with _roadmap_command_lifecycle(
        repo_root=repo_root,
        plans_dir=plans_dir,
        slug=slug,
        run_logger=None,
        flags={"mode": "refresh-seeds"},
        context=context,
    ) as lifecycle:
        run_logger = lifecycle.run_logger
        try:
            changes: list[RoadmapSeedRefreshChange] = []
            failures: list[RoadmapSeedRefreshFailure] = []
            try:
                artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=slug)
                _materialize_seed_rows(
                    slug,
                    artifact.plans,
                    repo_root=repo_root,
                    plans_dir=plans_dir,
                    run_logger=run_logger,
                    changes=changes,
                    failures=failures,
                    invoker=invoker,
                    max_attempts=max_stage_attempts,
                    writer_token=writer_token,
                )
            except (RoadmapError, RoadmapArtifactError):
                # A row can fail after earlier rows already succeeded and
                # wrote files — report what landed instead of discarding it,
                # and reserve "preflight-refused" for when nothing ran at
                # all. "error" (not a new outcome) is the documented closed
                # vocabulary's label for an unexpected post-start failure.
                if changes or failures:
                    write_seed_refresh_report(slug, changes, failures, plans_dir=plans_dir)
                    lifecycle.complete(outcome="error", rc=1)
                else:
                    lifecycle.complete(outcome="preflight-refused", rc=2)
                raise

            report_path = write_seed_refresh_report(slug, changes, failures, plans_dir=plans_dir)
            if not failures:
                outcome = SEED_REFRESH_OUTCOME_APPLIED
                lifecycle_outcome = "completed"
                rc = 0
            elif changes:
                outcome = SEED_REFRESH_OUTCOME_PARTIAL
                lifecycle_outcome = "partial"
                rc = 3
            else:
                outcome = SEED_REFRESH_OUTCOME_EXHAUSTED
                lifecycle_outcome = "exhausted"
                rc = 1
            lifecycle.complete(outcome=lifecycle_outcome, rc=rc)
            return RoadmapSeedRefreshResult(
                outcome=outcome,
                changes=tuple(changes),
                failures=tuple(failures),
                report_path=report_path,
            )
        except KeyboardInterrupt:
            if lifecycle.outcome is None:
                lifecycle.complete(outcome="interrupted", rc=130)
            raise
        except BaseException:
            # Keep command failures distinct from exhausted rows and avoid
            # serializing exception-derived seed or backend content.
            if lifecycle.outcome is None:
                lifecycle.complete(outcome="error", rc=1)
            raise
