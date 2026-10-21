"""Pure-I/O event-log primitives for ``plan-tool`` runs.

Provides frozen event dataclasses (``RunStart``, ``PhaseStart`` / ``End``,
``ClaudeCallStart`` / ``End``, ``ParseFailure``, ``CheckpointHit`` /
``Save`` / ``Discard``, ``IterationStart`` / ``End``, ``RunEnd``), an
atomic JSONL appender, and an atomic in-flight snapshot writer / reader.
Every subsequent step in the "Run Log Structured Events" plan
(``shell`` meta tee, ``create`` / ``detail`` / ``run`` wiring, the
``plan-tool runs`` subcommand) builds on these primitives.

This module is intentionally narrow:

- no claude shell-out (callers in later steps own that),
- no CLI surface (the ``plan-tool runs`` subcommand lands in step 6),
- no first-party ``plan_tool.*`` imports at module level, other than a
  ``TYPE_CHECKING``-only import for annotations (keeps the runtime
  dependency graph a tree — siblings ``checkpoint``/``run_log`` do not
  import each other); a few methods import ``plan_tool.shell``/
  ``plan_tool.telemetry`` locally instead, for the same reason,
- no third-party dependencies — JSONL on disk avoids pulling
  ``pydantic`` / ``yaml`` into a contract that's write-once-read-many.

Run logs live under ``<repo_root>/.plan-tool/runs/<slug>/``, sibling to
``.plan-tool/checkpoints/<slug>/`` (see ``checkpoint.CHECKPOINTS_REL``).

**Atomicity of ``append_event``.** POSIX ``write(2)`` guarantees that a
single ``O_APPEND`` write of at most ``PIPE_BUF`` bytes (4096 on
Linux/macOS) cannot interleave with another concurrent appender. We
size-check each serialized event against ``_MAX_LINE_BYTES`` and raise
``RunLogLineTooLarge`` rather than risk a torn write. On non-POSIX
platforms this falls back to a best-effort append; the plan-tool
runtime target is POSIX.

**Atomicity of ``write_in_flight``.** Same pattern as
``checkpoint.save_checkpoint`` — write a sibling tempfile in the target
directory, ``os.replace`` it into place. The previous snapshot (or
nothing) survives a crash mid-write. ``RunLogWriter`` holds one snapshot
dict per instance and keeps it current for a call's whole life: every
refresh (phase start, backend spawn, heartbeat, termination, recovery
wait) merges its fields into the held dict under a per-writer lock and
rewrites the file, so a stale field from an earlier refresh is never
lost and a late heartbeat can never overwrite a newer terminal status —
see ``RunLogWriter._refresh_in_flight``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Iterator,
    Mapping,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TYPE_CHECKING,
    get_args,
    runtime_checkable,
)

if TYPE_CHECKING:
    from plan_tool.model_response_sidecar import ModelResponseSidecarResult


RUN_LOG_SCHEMA_VERSION = 2

_ROADMAP_ESCALATION_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
_ROADMAP_ESCALATION_SHA256_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)

RUNS_REL = (".plan-tool", "runs")

IN_FLIGHT_FILENAME = "in-flight.json"

# ``status`` vocabulary for the in-flight snapshot (see ``RunLogWriter``'s
# ``_refresh_in_flight``). ``running`` is the default from ``start()`` and
# what ``phase_start``/``backend_spawn`` return to after a retry wait or a
# prior call's termination; ``awaiting_retry`` distinguishes the shared
# rate-limit/transient recovery loop's intentional sleep
# (``backend_recovery_wait``) from a call actually being over;
# ``backend_terminated`` is set by ``backend_termination``.
IN_FLIGHT_STATUS_RUNNING = "running"
IN_FLIGHT_STATUS_AWAITING_RETRY = "awaiting_retry"
IN_FLIGHT_STATUS_TERMINATED = "backend_terminated"

# POSIX ``write(2)`` guarantees atomicity for ``O_APPEND`` writes up to
# ``PIPE_BUF`` bytes (typically 4096 on Linux/macOS). Events larger
# than this raise rather than risk an interleaved record under
# concurrent appenders. A truncated event is worse than a missing one:
# downstream tooling like ``plan-tool runs diff`` would silently
# miscount tokens. See
# https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html
_MAX_LINE_BYTES = 4096

# Cap for any single string field inside a serialized event payload.
# Set well below ``_MAX_LINE_BYTES`` so one large field cannot
# single-handedly blow the line cap (the original failure mode was
# ``argv`` containing a long ``--from "<description>"`` value).
# Strings longer than this are truncated and the elision is recorded
# inline so ``plan-tool runs show`` makes it obvious the event was
# abridged for storage.
_MAX_STRING_LEN_IN_PAYLOAD = 1024
_ELISION_RESERVED = 48  # room for the trailing ``…<elided N chars>`` marker

# Budget for an event's one bounded list — ``gate_violations``' ``violations``
# — counted in *serialized* bytes. Gate messages are prose and an artifact breaking many
# rows produces many of them, so whole strings are dropped rather than cut
# mid-sentence — a half message reads as a different complaint than the one
# the gate made, and a half id matches nothing. Set so the list plus the
# event's other fields cannot reach ``_MAX_LINE_BYTES``: an observability
# event must never break the run it observes by raising
# ``RunLogLineTooLarge``.
_MAX_VIOLATION_BYTES_IN_PAYLOAD = 2048

# Process-local guard around the ``O_APPEND`` write in
# ``_append_jsonl_line``. POSIX already makes a single ``O_APPEND`` write of
# at most ``PIPE_BUF`` (== ``_MAX_LINE_BYTES``) bytes atomic across
# appenders, so cross-process safety doesn't rely on this lock. It exists so
# that when ``detail``'s concurrent authoring pool (``jobs > 1``) has several
# worker threads emitting per-attempt events into the same log, the write
# stays whole regardless of platform ``write(2)`` semantics — the one shared
# mutable resource a worker thread touches.
_APPEND_LOCK = threading.Lock()

# The lockfile covers a snapshot's replace/read/unlink lifecycle.  The
# process-local lock supplements advisory locks, which do not reliably
# contend between distinct descriptors in every runtime.
_IN_FLIGHT_GUARDS_LOCK = threading.Lock()
_IN_FLIGHT_GUARDS: dict[Path, threading.Lock] = {}

try:  # POSIX is the supported CLI runtime.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback below.
    _fcntl = None

try:  # Windows keeps the best available cross-process guard.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - POSIX has fcntl.
    _msvcrt = None


# ---------- event dataclasses ----------


@dataclass(frozen=True)
class _BaseEvent:
    """Fields stamped on every event regardless of kind.

    ``ts`` is ISO-8601 UTC seconds-precision (matches the
    ``created_at`` convention in ``checkpoint.py``). ``run_id`` is the
    caller-chosen opaque identifier shared across every event in a
    single ``plan-tool`` invocation — also the JSONL filename.
    ``event`` is the string discriminator (e.g. ``"run_start"``);
    it's declared last so subclasses can redefine it with a default
    without violating dataclass field-ordering rules (a redefined
    field keeps its base position, so ``event`` must come after any
    other no-default base field).
    """

    ts: str
    run_id: str
    event: str

    # Field names this event's payload omits (rather than serializes as
    # JSON null) when their value is None — read generically by ``_emit``,
    # and cross-checked against data_contract.py's ``conditionally_persisted``
    # by ``tests/test_data_contract.py`` so the two can't drift apart.
    omit_when_none: ClassVar[frozenset[str]] = frozenset()


@dataclass(frozen=True)
class RunStart(_BaseEvent):
    schema_version: int = RUN_LOG_SCHEMA_VERSION
    command: str = ""
    plan_slug: str = ""
    argv: list[str] = field(default_factory=list)
    pid: int = 0
    cwd: str = ""
    event: str = "run_start"


@dataclass(frozen=True)
class PhaseStart(_BaseEvent):
    phase: str = ""
    event: str = "phase_start"


@dataclass(frozen=True)
class PhaseEnd(_BaseEvent):
    phase: str = ""
    duration_ms: int = 0
    outcome: str = ""
    event: str = "phase_end"


@dataclass(frozen=True)
class ClaudeCallStart(_BaseEvent):
    phase: str = ""
    attempt: int = 1
    prompt_bytes: int = 0
    # Hex SHA-256 of the prompt text; never the text. ``None`` = the caller did
    # not supply one. Events written before 2026-10-16 lack the key entirely.
    prompt_sha256: Optional[str] = None
    event: str = "claude_call_start"


@dataclass(frozen=True)
class ClaudeCallEnd(_BaseEvent):
    phase: str = ""
    attempt: int = 1
    rc: int = 0
    duration_ms: int = 0
    stdout_bytes: int = 0
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    request_id: Optional[str] = None
    cost_usd: Optional[float] = None
    # True: ``tokens_input`` includes cached tokens (codex). False: it excludes
    # them (claude). ``None``: not established (cursor, older events).
    input_includes_cached: Optional[bool] = None
    event: str = "claude_call_end"


@dataclass(frozen=True)
class ClaudeStreamEvent(_BaseEvent):
    """One parsed event from ``claude -p --output-format stream-json``.

    Step 2 of the Claude Call Observability plan emits one of these per
    NDJSON line that crosses the stdout pump while a ``claude -p`` call
    is in flight (``tool_use``, ``tool_result``, ``assistant_text``,
    ``system``, ``result``). The intent is per-tool visibility *during*
    the call — between ``claude_call_start`` and ``claude_call_end`` the
    run-log used to be silent.

    ``tool_input_summary`` is a 200-char preview (``Edit``/``Write``/
    ``Read`` → ``file_path``, ``Bash`` → ``command``, ``Grep`` →
    ``pattern in path``) so the JSONL line stays well under the
    ``_MAX_LINE_BYTES`` cap even when a tool input is a long shell
    command or file path. The full input is recoverable from the
    sibling stream log (docs/how-to/pipeline/run.md).
    """

    phase: str = ""
    attempt: int = 1
    kind: str = ""
    tool_name: Optional[str] = None
    tool_input_summary: Optional[str] = None
    bytes_in_delta: int = 0
    event: str = "claude_stream_event"


@dataclass(frozen=True)
class ClaudeCallProgress(_BaseEvent):
    """Periodic heartbeat emitted by the step-2 progress daemon thread.

    Persisted to the JSONL (not just the terminal heartbeat) so an
    operator looking at a stale run can answer "was the subprocess
    still doing work?" without scraping terminal scrollback.
    ``silent_ms`` is the wall-clock since the last
    :class:`ClaudeStreamEvent` was observed; ``last_tool`` /
    ``last_activity_kind`` pin the most recent activity so the same
    line surfaces "stuck on a long Bash" vs. "no events at all".
    """

    phase: str = ""
    attempt: int = 1
    elapsed_ms: int = 0
    silent_ms: int = 0
    last_tool: Optional[str] = None
    last_activity_kind: Optional[str] = None
    event: str = "claude_call_progress"


@dataclass(frozen=True)
class ClaudeCallStallSuspected(_BaseEvent):
    """One-shot signal that ``silent_ms`` crossed ``STALL_THRESHOLD_S``.

    Fired at most once per ``(phase, attempt)`` pair by the step-2
    progress daemon — recurring heartbeats remain
    :class:`ClaudeCallProgress`. Downstream tooling (``runs profile``
    in step 5, an operator scanning the JSONL) treats the presence of
    this event as the load-bearing "investigate this run" marker.
    """

    phase: str = ""
    attempt: int = 1
    silent_ms: int = 0
    threshold_ms: int = 0
    last_tool: Optional[str] = None
    event: str = "claude_call_stall_suspected"


@dataclass(frozen=True)
class ParseFailure(_BaseEvent):
    phase: str = ""
    attempt: int = 1
    failure_path: str = ""
    event: str = "parse_failure"


@dataclass(frozen=True)
class AttemptFailed(_BaseEvent):
    """Which failure kind consumed one attempt.

    Emitted for **every** kind, gates included, so the kind is readable
    without unioning event types. ``failure_kind`` is an open string: the
    vocabulary is the producer's (``roadmap.py``'s ``FAILURE_*``), above this
    leaf. See docs in `DATA_CONTRACT.md`.
    """

    phase: str = ""
    attempt: int = 1
    failure_kind: str = ""
    event: str = "attempt_failed"


@dataclass(frozen=True)
class ModelFailureReceipt(_BaseEvent):
    """Redacted identity and sidecar availability for a rejected response."""

    phase: str = ""
    attempt: int = 1
    reason: str = ""
    response_bytes: Optional[int] = None
    response_sha256: Optional[str] = None
    sidecar_disposition: str = "no-response"
    sidecar_path: Optional[str] = None
    event: str = "model_failure_receipt"

    omit_when_none: ClassVar[frozenset[str]] = frozenset({"sidecar_path"})


@dataclass(frozen=True)
class GateViolations(_BaseEvent):
    """What a gated stage's failed attempt was told to fix.

    ``violation_count`` is always the exact total; ``violations`` carries
    whole messages up to the payload budget and ``violations_omitted``
    counts the ones that did not fit.
    """

    phase: str = ""
    attempt: int = 1
    violation_count: int = 0
    violations: list[str] = field(default_factory=list)
    violations_omitted: int = 0
    event: str = "gate_violations"


@dataclass(frozen=True)
class BackendSpawn(_BaseEvent):
    """That a backend child process is about to run.

    ``transport``/``child_pid``/``effective_timeout_ms``/``prompt_bytes`` are
    populated by ``backend_runner.run_streaming_once``, the sole producer for
    both the streaming and batch lanes (``shell.claude_invoke`` routes both
    through it).
    """

    phase: str = ""
    attempt: int = 1
    backend: str = ""
    transport: Optional[str] = None
    child_pid: Optional[int] = None
    effective_timeout_ms: Optional[int] = None
    prompt_bytes: Optional[int] = None
    stream_log: Optional[str] = None
    event: str = "backend_spawn"


@dataclass(frozen=True)
class BackendTermination(_BaseEvent):
    """How a backend child process ended.

    ``reason`` is an open string — the producer's vocabulary, above this
    leaf, following ``AttemptFailed.failure_kind``'s convention rather than
    importing a closed vocabulary. ``signal_or_timeout`` and ``silent_ms``
    are populated by ``backend_runner.run_streaming_once`` for both the
    streaming and batch lanes.
    """

    phase: str = ""
    attempt: int = 1
    backend: str = ""
    reason: str = ""
    duration_ms: int = 0
    signal_or_timeout: Optional[str] = None
    silent_ms: Optional[int] = None
    event: str = "backend_termination"


@dataclass(frozen=True)
class RunInterrupted(_BaseEvent):
    """That an operator interrupt (Ctrl-C) landed during ``source``.

    Every row of this kind *is* an operator interrupt by construction, so
    there is deliberately no ``reason`` field. ``signal`` is a fixed label
    reserved for a future non-SIGINT source, not classification work.
    """

    phase: str = ""
    attempt: int = 1
    source: str = ""
    signal: str = "SIGINT"
    event: str = "run_interrupted"


@dataclass(frozen=True)
class BackendRecoveryWait(_BaseEvent):
    """That the shared rate-limit/transient recovery loop is sleeping
    between attempts, not hung.

    ``next_attempt`` is the upcoming retry's ordinal number, matching the
    ``attempt`` field every other call event already carries — not a
    timestamp. ``delay_ms`` carries the wait's duration.
    """

    phase: str = ""
    attempt: int = 1
    reason: str = ""
    delay_ms: int = 0
    next_attempt: int = 0
    backend: str = ""
    event: str = "backend_recovery_wait"


@dataclass(frozen=True)
class RoadmapPreflightFailed(_BaseEvent):
    """A roadmap stage run stopped before it could invoke a stage.

    ``check`` is a bounded producer-owned category such as ``"brief_source"``
    or ``"accepted_head"``. The error's prose remains on ``run_end`` / stderr;
    this event makes its operational class queryable without duplicating it.
    """

    check: str = ""
    event: str = "roadmap_preflight_failed"


@dataclass(frozen=True)
class RoadmapStageWritten(_BaseEvent):
    """One accepted roadmap artifact write and its durable effects."""

    phase: str = ""
    stage: int = 0
    artifact_path: str = ""
    artifact_digest: str = ""
    replaced: bool = False
    draft_seed_count: int = 0
    event: str = "roadmap_stage_written"


@dataclass(frozen=True)
class RoadmapSeedApplyResult(_BaseEvent):
    """The outcome and aggregate effects of an apply-only seed promotion."""

    outcome: str = ""
    target_count: int = 0
    promotion_count: int = 0
    collision_count: int = 0
    missing_draft_count: int = 0
    malformed_draft_count: int = 0
    stale_draft_count: int = 0
    path_escaping_draft_count: int = 0
    duplicate_draft_count: int = 0
    digest_mismatched_draft_count: int = 0
    event: str = "roadmap_seed_apply_result"


@dataclass(frozen=True)
class RoadmapStructuralRevisionPreflight(_BaseEvent):
    """Closed structural-revision admission facts without source content."""

    receipt_final: Optional[str] = None
    analysis_final: Optional[str] = None
    artifact_key: Optional[str] = None
    feedback_id: Optional[str] = None
    target_row_id: Optional[str] = None
    binding_digest: Optional[str] = None
    render_canonical: Optional[bool] = None
    verdict: Literal[
        "mode-rejected",
        "evaluator-rejected",
        "evidence-rejected",
        "changed-brief",
        "legacy-brief",
        "feedback-rejected",
        "render-canonical-rejected",
        "enrolled-roadmap-rejected",
        "accepted",
        "interrupted",
    ] = "interrupted"
    event: str = "roadmap_structural_revision_preflight"


@dataclass(frozen=True)
class RoadmapStructuralRevisionAttempt(_BaseEvent):
    """One redacted terminal structural-revision attempt."""

    attempt: Literal[1] = 1
    binding_digest: str = ""
    invalidated_seed_count: Optional[int] = None
    operation_verdict: Literal["not-reached", "accepted", "rejected"] = "not-reached"
    merge_verdict: Literal["not-reached", "accepted", "rejected"] = "not-reached"
    proof_verdict: Literal["not-reached", "structural-rejected", "gate-rejected", "accepted"] = (
        "not-reached"
    )
    final_snapshot_verdict: Literal["not-reached", "current", "stale"] = "not-reached"
    publication_outcome: Literal[
        "not-reached", "published", "failed", "unknown-after-interrupt"
    ] = "not-reached"
    outcome: Literal[
        "invoke-failed",
        "empty-reply",
        "envelope-rejected",
        "merge-rejected",
        "proof-rejected",
        "final-snapshot-stale",
        "changed-brief",
        "legacy-brief",
        "publication-failed",
        "published",
        "interrupted",
    ] = "interrupted"
    event: str = "roadmap_structural_revision_attempt"


@dataclass(frozen=True)
class RoadmapEscalationPreflight(_BaseEvent):
    """Receipt admission facts, without raw command or reviewer content."""

    artifact_key: Optional[str] = None
    feedback_id: Optional[str] = None
    # Hand-copied from roadmap_escalation_selection.ReceiptReason rather than
    # imported: this module's own invariant (see module docstring) is no
    # first-party plan_tool.* imports, keeping the dependency graph a tree —
    # not an import-cycle constraint (no cycle exists here to begin with).
    reason: Optional[
        Literal[
            "prose",
            "row-structure",
            "collection-structure",
            "relationship-semantics",
            "decision-semantics",
            "cross-artifact-impact",
        ]
    ] = None
    target_kind: Optional[Literal["artifact", "row"]] = None
    target_id: Optional[str] = None
    artifact_digest: Optional[str] = None
    verdict: Literal[
        "mode-rejected",
        "malformed-selector",
        "unknown-artifact",
        "identifier-rejected",
        "reason-rejected",
        "artifact-unreadable",
        "artifact-unparsable",
        "artifact-not-current",
        "missing-feedback",
        "duplicate-feedback",
        "not-open",
        "already-responded",
        "missing-or-ambiguous-target",
        "target-not-live-in-selected-artifact",
        "accepted",
        "interrupted",
    ] = "interrupted"
    event: str = "roadmap_escalation_preflight"


@dataclass(frozen=True)
class RoadmapEscalationResult(_BaseEvent):
    """One terminal receipt lifecycle outcome with no reviewer prose."""

    outcome: Literal[
        "preflight-rejected",
        "storage-rejected",
        "created",
        "committed-existing",
        "reused",
        "collision",
        "invalid-existing-receipt",
        "write-failed",
        "commit-failed",
        "interrupted",
    ] = "interrupted"
    receipt_id: Optional[str] = None
    handoff: Optional[Literal["requires-scope-review"]] = None
    event: str = "roadmap_escalation_result"


@dataclass(frozen=True)
class RoadmapImpactPreflight(_BaseEvent):
    """Impact-analysis admission facts, without evidence content or paths."""

    receipt_final: Optional[str] = None
    artifact_key: Optional[str] = None
    feedback_id: Optional[str] = None
    reason: Optional[
        Literal[
            "prose",
            "row-structure",
            "collection-structure",
            "relationship-semantics",
            "decision-semantics",
            "cross-artifact-impact",
        ]
    ] = None
    target_kind: Optional[Literal["artifact", "row"]] = None
    target_id: Optional[str] = None
    receipt_source_digest: Optional[str] = None
    source_record_digest: Optional[str] = None
    brief_digest: Optional[str] = None
    snapshot_artifact_count: Optional[int] = None
    closure_node_count: Optional[int] = None
    closure_relation_count: Optional[int] = None
    closure_mapping_failures: Optional[tuple[tuple[int, int, int], ...]] = None
    verdict: Literal[
        "mode-rejected",
        "final-rejected",
        "receipt-missing",
        "receipt-unreadable",
        "receipt-invalid",
        "receipt-rejected",
        "changed-brief",
        "legacy-brief",
        "snapshot-rejected",
        "closure-rejected",
        "accepted",
        "interrupted",
    ] = "interrupted"
    event: str = "roadmap_impact_preflight"


@dataclass(frozen=True)
class RoadmapImpactResult(_BaseEvent):
    """One terminal impact-analysis outcome with no evidence content."""

    outcome: Literal[
        "completed",
        "preflight-rejected",
        "changed-brief",
        "legacy-brief",
        "invalid",
        "storage-rejected",
        "collision",
        "write-failed",
        "interrupted",
    ] = "interrupted"
    analysis_id: Optional[str] = None
    route_class: Optional[Literal["same-artifact", "cross-artifact", "requires-scope-review"]] = (
        None
    )
    publication_outcome: Optional[Literal["created", "reused"]] = None
    next_workflow: Optional[
        Literal[
            "roadmap-same-artifact-structural-revision",
            "roadmap-cross-artifact-revision-transaction",
        ]
    ] = None
    event: str = "roadmap_impact_result"


_AUDIT_PASS_IDS_CAP = 40


@dataclass(frozen=True)
class AuditPassEnd(_BaseEvent):
    """One conceptual-audit sampling pass: the finding ids it added.

    ``new_ids`` are the stable ids first seen this pass (carried findings are
    excluded); ``material_new_ids`` is the subset counted as material. Neutral
    passes (errored, skipped) record ``outcome`` and leave materiality empty.
    """

    pass_number: int = 0
    cap: int = 0
    outcome: str = ""
    # Counts are exact; the id lists are capped (``_AUDIT_PASS_IDS_CAP``) so one
    # line stays under ``_MAX_LINE_BYTES``. A count above ``len(ids)`` = truncated.
    new_count: int = 0
    material_new_count: int = 0
    new_ids: list[str] = field(default_factory=list)
    material_new_ids: list[str] = field(default_factory=list)
    unique_so_far: int = 0
    event: str = "audit_pass_end"


@dataclass(frozen=True)
class CheckpointHit(_BaseEvent):
    name: str = ""
    input_hash: str = ""
    payload_bytes: int = 0
    event: str = "checkpoint_hit"


@dataclass(frozen=True)
class CheckpointSave(_BaseEvent):
    name: str = ""
    input_hash: str = ""
    payload_bytes: int = 0
    event: str = "checkpoint_save"


@dataclass(frozen=True)
class CheckpointDiscard(_BaseEvent):
    name: str = ""
    reason: str = ""
    event: str = "checkpoint_discard"


@dataclass(frozen=True)
class IterationStart(_BaseEvent):
    step_id: int = 0
    step_title: str = ""
    event: str = "iteration_start"


@dataclass(frozen=True)
class IterationEnd(_BaseEvent):
    step_id: int = 0
    duration_ms: int = 0
    outcome: str = ""
    event: str = "iteration_end"


@dataclass(frozen=True)
class RunEnd(_BaseEvent):
    duration_ms: int = 0
    outcome: str = ""
    rc: int = 0
    event: str = "run_end"


Event = (
    RunStart
    | PhaseStart
    | PhaseEnd
    | ClaudeCallStart
    | ClaudeCallEnd
    | ClaudeStreamEvent
    | ClaudeCallProgress
    | ClaudeCallStallSuspected
    | ParseFailure
    | AttemptFailed
    | ModelFailureReceipt
    | GateViolations
    | BackendSpawn
    | BackendTermination
    | RunInterrupted
    | BackendRecoveryWait
    | RoadmapPreflightFailed
    | RoadmapStageWritten
    | RoadmapSeedApplyResult
    | RoadmapStructuralRevisionPreflight
    | RoadmapStructuralRevisionAttempt
    | RoadmapEscalationPreflight
    | RoadmapEscalationResult
    | RoadmapImpactPreflight
    | RoadmapImpactResult
    | AuditPassEnd
    | CheckpointHit
    | CheckpointSave
    | CheckpointDiscard
    | IterationStart
    | IterationEnd
    | RunEnd
)


# A context envelope must never take authority away from an event or the
# snapshot lifecycle. ``command`` is the one exception: ``start()`` owns it
# and propagates that fixed value with a context-enabled writer.
_CONTEXT_RESERVED_KEYS = (
    frozenset(key for event_type in get_args(Event) for key in event_type.__dataclass_fields__)
    | {
        "started_at",
        "log_path",
        "status",
        "current_phase",
        "last_event_ts",
    }
) - {"command"}

# The envelope is only ever shallow-copied (``dict(context)``) as it's read
# and updated. Restricting values to immutable scalars makes that copy a
# real isolation boundary instead of one that would silently alias a future
# mutable value between the writer and a caller's own reference to it.
_CONTEXT_SCALAR_TYPES = (str, bool, int, float, type(None))


def _validate_context_values(fields: Mapping[str, Any]) -> None:
    for key, value in fields.items():
        if not isinstance(value, _CONTEXT_SCALAR_TYPES):
            raise TypeError(
                f"context field {key!r} must be one of {_CONTEXT_SCALAR_TYPES}, "
                f"got {type(value).__name__}"
            )


def _validate_roadmap_escalation_preflight_facts(
    *,
    artifact_key: Optional[str],
    feedback_id: Optional[str],
    reason: Optional[str],
    target_kind: Optional[str],
    target_id: Optional[str],
    artifact_digest: Optional[str],
    verdict: str,
) -> None:
    """Keep receipt lifecycle facts monotonic and structurally redacted."""
    selector_resolved = artifact_key is not None or feedback_id is not None
    if selector_resolved:
        if (
            not isinstance(artifact_key, str)
            or not isinstance(feedback_id, str)
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(artifact_key) is None
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(feedback_id) is None
        ):
            raise ValueError("roadmap escalation selector facts must be receipt-safe")
    if reason is not None and not selector_resolved:
        raise ValueError("roadmap escalation reason requires a resolved selector")
    if artifact_digest is not None and (
        reason is None
        or not isinstance(artifact_digest, str)
        or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(artifact_digest) is None
    ):
        raise ValueError("roadmap escalation digest requires a closed reason")

    target_resolved = target_kind is not None or target_id is not None
    if target_resolved:
        if (
            target_kind not in {"artifact", "row"}
            or not isinstance(target_id, str)
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(target_id) is None
            or artifact_digest is None
        ):
            raise ValueError("roadmap escalation target facts require accepted evidence")

    if verdict in {
        "mode-rejected",
        "malformed-selector",
        "unknown-artifact",
        "interrupted",
    }:
        required = (None, None, None, None, None, None)
    elif verdict == "identifier-rejected":
        permitted = {
            (None, None, None, None, None, None),
            ("selector", "selector", "reason", None, None, "digest"),
        }
        actual = (
            "selector" if artifact_key is not None else None,
            "selector" if feedback_id is not None else None,
            "reason" if reason is not None else None,
            "target" if target_kind is not None else None,
            "target" if target_id is not None else None,
            "digest" if artifact_digest is not None else None,
        )
        if actual not in permitted:
            raise ValueError("roadmap escalation identifier rejection leaked later facts")
        return
    elif verdict == "reason-rejected":
        required = ("selector", "selector", None, None, None, None)
    elif verdict == "artifact-unreadable":
        required = ("selector", "selector", "reason", None, None, None)
    elif verdict in {
        "artifact-unparsable",
        "artifact-not-current",
        "missing-feedback",
        "duplicate-feedback",
        "not-open",
        "already-responded",
        "missing-or-ambiguous-target",
        "target-not-live-in-selected-artifact",
    }:
        required = ("selector", "selector", "reason", None, None, "digest")
    elif verdict == "accepted":
        required = ("selector", "selector", "reason", "target", "target", "digest")
    else:  # The caller validates the closed verdict vocabulary first.
        return

    actual = (
        "selector" if artifact_key is not None else None,
        "selector" if feedback_id is not None else None,
        "reason" if reason is not None else None,
        "target" if target_kind is not None else None,
        "target" if target_id is not None else None,
        "digest" if artifact_digest is not None else None,
    )
    if actual != required:
        raise ValueError("roadmap escalation preflight facts do not match its verdict")


def _validate_roadmap_structural_revision_preflight_facts(
    *,
    receipt_final: Optional[str],
    analysis_final: Optional[str],
    artifact_key: Optional[str],
    feedback_id: Optional[str],
    target_row_id: Optional[str],
    binding_digest: Optional[str],
    render_canonical: Optional[bool],
    verdict: str,
) -> None:
    """Keep structural admission facts complete, ordered, and redacted."""
    finals = (receipt_final, analysis_final)
    if any(value is not None for value in finals):
        if not all(isinstance(value, str) for value in finals) or any(
            _ROADMAP_ESCALATION_SHA256_RE.fullmatch(value) is None for value in finals
        ):
            raise ValueError(
                "roadmap structural revision final identities must be a complete SHA-256 pair"
            )

    selection = (artifact_key, feedback_id)
    if any(value is not None for value in selection):
        if (
            receipt_final is None
            or analysis_final is None
            or not all(isinstance(value, str) for value in selection)
            or any(_ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(value) is None for value in selection)
        ):
            raise ValueError(
                "roadmap structural revision selection facts require complete safe evidence"
            )

    if target_row_id is not None and (
        artifact_key is None
        or feedback_id is None
        or not isinstance(target_row_id, str)
        or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(target_row_id) is None
    ):
        raise ValueError("roadmap structural revision target requires complete safe selection")
    if render_canonical is not None and type(render_canonical) is not bool:
        raise ValueError("roadmap structural revision canonicality must be boolean or null")
    if render_canonical is not None and target_row_id is None:
        raise ValueError("roadmap structural revision canonicality requires a resolved target")
    if binding_digest is not None and (
        render_canonical is not True
        or not isinstance(binding_digest, str)
        or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(binding_digest) is None
    ):
        raise ValueError("roadmap structural revision binding requires accepted canonicality")

    expected_facts = {
        "mode-rejected": (None, None, None, None, None, None, None),
        "evaluator-rejected": (None, None, None, None, None, None, None),
        "enrolled-roadmap-rejected": (None, None, None, None, None, None, None),
        "interrupted": (None, None, None, None, None, None, None),
        "evidence-rejected": ("final", "final", None, None, None, None, None),
        "changed-brief": ("final", "final", None, None, None, None, None),
        "legacy-brief": ("final", "final", None, None, None, None, None),
        "feedback-rejected": (
            "final",
            "final",
            "selection",
            "selection",
            None,
            None,
            None,
        ),
        "render-canonical-rejected": (
            "final",
            "final",
            "selection",
            "selection",
            "target",
            None,
            False,
        ),
        "accepted": (
            "final",
            "final",
            "selection",
            "selection",
            "target",
            "binding",
            True,
        ),
    }.get(verdict)
    if expected_facts is None:
        return  # The writer validates the closed verdict vocabulary first.
    actual_facts = (
        "final" if receipt_final is not None else None,
        "final" if analysis_final is not None else None,
        "selection" if artifact_key is not None else None,
        "selection" if feedback_id is not None else None,
        "target" if target_row_id is not None else None,
        "binding" if binding_digest is not None else None,
        render_canonical,
    )
    if actual_facts != expected_facts:
        raise ValueError("roadmap structural revision preflight facts do not match its verdict")


def _validate_roadmap_structural_revision_attempt(
    *,
    attempt: int,
    binding_digest: str,
    invalidated_seed_count: Optional[int],
    operation_verdict: str,
    merge_verdict: str,
    proof_verdict: str,
    final_snapshot_verdict: str,
    publication_outcome: str,
    outcome: str,
) -> None:
    """Require one terminal outcome to match its completed phase prefix."""
    if type(attempt) is not int or attempt != 1:
        raise ValueError("structural revision attempts are always attempt 1")
    if (
        not isinstance(binding_digest, str)
        or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(binding_digest) is None
    ):
        raise ValueError("structural revision attempts require a SHA-256 binding digest")
    if invalidated_seed_count is not None and (
        type(invalidated_seed_count) is not int or invalidated_seed_count < 0
    ):
        raise ValueError("invalidated seed count must be a nonnegative integer or null")

    allowed = {
        "operation_verdict": {"not-reached", "accepted", "rejected"},
        "merge_verdict": {"not-reached", "accepted", "rejected"},
        "proof_verdict": {
            "not-reached",
            "structural-rejected",
            "gate-rejected",
            "accepted",
        },
        "final_snapshot_verdict": {"not-reached", "current", "stale"},
        "publication_outcome": {
            "not-reached",
            "published",
            "failed",
            "unknown-after-interrupt",
        },
    }
    values = {
        "operation_verdict": operation_verdict,
        "merge_verdict": merge_verdict,
        "proof_verdict": proof_verdict,
        "final_snapshot_verdict": final_snapshot_verdict,
        "publication_outcome": publication_outcome,
    }
    for name, value in values.items():
        if value not in allowed[name]:
            raise ValueError(f"invalid structural revision {name}: {value!r}")

    terminal_rows = {
        "invoke-failed": (
            "not-reached",
            "not-reached",
            "not-reached",
            "not-reached",
            "not-reached",
        ),
        "empty-reply": (
            "not-reached",
            "not-reached",
            "not-reached",
            "not-reached",
            "not-reached",
        ),
        "envelope-rejected": (
            "rejected",
            "not-reached",
            "not-reached",
            "not-reached",
            "not-reached",
        ),
        "merge-rejected": (
            "accepted",
            "rejected",
            "not-reached",
            "not-reached",
            "not-reached",
        ),
        "final-snapshot-stale": (
            "accepted",
            "accepted",
            "accepted",
            "stale",
            "not-reached",
        ),
        "changed-brief": (
            "accepted",
            "accepted",
            "accepted",
            "stale",
            "not-reached",
        ),
        "legacy-brief": (
            "accepted",
            "accepted",
            "accepted",
            "stale",
            "not-reached",
        ),
        "publication-failed": (
            "accepted",
            "accepted",
            "accepted",
            "current",
            "failed",
        ),
        "published": (
            "accepted",
            "accepted",
            "accepted",
            "current",
            "published",
        ),
    }
    phases = (
        operation_verdict,
        merge_verdict,
        proof_verdict,
        final_snapshot_verdict,
        publication_outcome,
    )
    if outcome == "proof-rejected":
        if phases not in {
            (
                "accepted",
                "accepted",
                "structural-rejected",
                "not-reached",
                "not-reached",
            ),
            (
                "accepted",
                "accepted",
                "gate-rejected",
                "not-reached",
                "not-reached",
            ),
        }:
            raise ValueError("proof rejection phases do not match structural outcome")
    elif outcome == "interrupted":
        permitted_prefixes = {
            ("not-reached", "not-reached", "not-reached", "not-reached", "not-reached"),
            ("accepted", "not-reached", "not-reached", "not-reached", "not-reached"),
            ("accepted", "accepted", "not-reached", "not-reached", "not-reached"),
            ("accepted", "accepted", "accepted", "not-reached", "not-reached"),
            ("accepted", "accepted", "accepted", "current", "not-reached"),
            (
                "accepted",
                "accepted",
                "accepted",
                "current",
                "unknown-after-interrupt",
            ),
        }
        if phases not in permitted_prefixes:
            raise ValueError("interrupted structural revision has an invalid phase prefix")
    elif outcome not in terminal_rows:
        raise ValueError(f"invalid structural revision outcome: {outcome!r}")
    elif phases != terminal_rows[outcome]:
        raise ValueError("structural revision phases do not match terminal outcome")

    if outcome == "published":
        if invalidated_seed_count is None:
            raise ValueError("published structural revision requires invalidated seed count")
    elif invalidated_seed_count is not None:
        raise ValueError("unsuccessful structural revision must not report invalidated seeds")


def _validate_roadmap_impact_preflight_facts(
    *,
    receipt_final: Optional[str],
    artifact_key: Optional[str],
    feedback_id: Optional[str],
    reason: Optional[str],
    target_kind: Optional[str],
    target_id: Optional[str],
    receipt_source_digest: Optional[str],
    source_record_digest: Optional[str],
    brief_digest: Optional[str],
    snapshot_artifact_count: Optional[int],
    closure_node_count: Optional[int],
    closure_relation_count: Optional[int],
    closure_mapping_failures: Optional[tuple[tuple[int, int, int], ...]],
    verdict: str,
) -> None:
    """Keep impact admission facts ordered and redacted."""
    if receipt_final is not None and (
        not isinstance(receipt_final, str)
        or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(receipt_final) is None
    ):
        raise ValueError("roadmap impact receipt final must be a SHA-256 identity")

    receipt_fields = (
        artifact_key,
        feedback_id,
        reason,
        target_kind,
        target_id,
        receipt_source_digest,
    )
    receipt_resolved = any(value is not None for value in receipt_fields)
    if receipt_resolved:
        if (
            receipt_final is None
            or not isinstance(artifact_key, str)
            or not isinstance(feedback_id, str)
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(artifact_key) is None
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(feedback_id) is None
            or target_kind not in {"artifact", "row"}
            or not isinstance(target_id, str)
            or _ROADMAP_ESCALATION_SAFE_ID_RE.fullmatch(target_id) is None
            or not isinstance(receipt_source_digest, str)
            or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(receipt_source_digest) is None
        ):
            raise ValueError("roadmap impact receipt facts must be complete and receipt-safe")

    snapshot_fields = (
        source_record_digest,
        brief_digest,
        snapshot_artifact_count,
    )
    snapshot_resolved = any(value is not None for value in snapshot_fields)
    if snapshot_resolved:
        if (
            not receipt_resolved
            or not isinstance(source_record_digest, str)
            or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(source_record_digest) is None
            or not isinstance(brief_digest, str)
            or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(brief_digest) is None
            or type(snapshot_artifact_count) is not int
            or snapshot_artifact_count < 0
        ):
            raise ValueError(
                "roadmap impact snapshot facts require a complete receipt and aggregates"
            )

    closure_fields = (
        closure_node_count,
        closure_relation_count,
        closure_mapping_failures,
    )
    closure_resolved = any(value is not None for value in closure_fields)
    if closure_resolved:
        if (
            not snapshot_resolved
            or type(closure_node_count) is not int
            or closure_node_count < 0
            or type(closure_relation_count) is not int
            or closure_relation_count < 0
            or not isinstance(closure_mapping_failures, tuple)
            or any(
                not isinstance(failure, tuple)
                or len(failure) != 3
                or any(type(value) is not int or value < 0 for value in failure)
                for failure in closure_mapping_failures
            )
        ):
            raise ValueError(
                "roadmap impact closure facts require a complete snapshot and safe diagnostics"
            )

    phase = (
        4
        if closure_resolved
        else 3
        if snapshot_resolved
        else 2
        if receipt_resolved
        else 1
        if receipt_final is not None
        else 0
    )
    maximum_phase = {
        "mode-rejected": 1,
        "final-rejected": 1,
        "receipt-missing": 1,
        "receipt-unreadable": 1,
        "receipt-invalid": 1,
        "receipt-rejected": 2,
        "changed-brief": 2,
        "legacy-brief": 2,
        "snapshot-rejected": 3,
        "closure-rejected": 4,
        "accepted": 4,
        "interrupted": 4,
    }.get(verdict)
    if maximum_phase is None:
        return  # The writer validates the closed verdict vocabulary first.
    if phase > maximum_phase:
        raise ValueError("roadmap impact preflight leaked facts from a later phase")
    if verdict == "accepted" and phase != 4:
        raise ValueError("accepted roadmap impact preflight requires all resolved facts")


# ---------- path helpers ----------


def runs_root(repo_root: Path) -> Path:
    """Return ``<repo_root>/.plan-tool/runs/``."""
    return repo_root.joinpath(*RUNS_REL)


def run_dir(repo_root: Path, slug: str) -> Path:
    """Return the per-plan-slug directory under the runs root."""
    return runs_root(repo_root) / slug


def run_log_path(repo_root: Path, slug: str, run_id: str) -> Path:
    """Return the JSONL log file path for a specific run."""
    return run_dir(repo_root, slug) / f"{run_id}.jsonl"


def prune_stream_logs(
    slug_dir: Path, *, older_than_seconds: Optional[int], now: Optional[float] = None
) -> list[Path]:
    """Remove ``<run_id>.streams/`` directories directly under ``slug_dir``.

    A directory goes when its newest file is older than the cutoff;
    ``None`` removes every one. Symlinks are skipped. See
    docs/how-to/pipeline/run.md "Raw backend stream log".
    """
    import shutil
    import time

    cutoff = None if older_than_seconds is None else (
        (time.time() if now is None else now) - older_than_seconds
    )
    removed: list[Path] = []
    if slug_dir.is_symlink() or not slug_dir.is_dir():
        return removed
    for streams in sorted(slug_dir.glob("*.streams")):
        if streams.is_symlink() or not streams.is_dir():
            continue
        if cutoff is not None:
            try:
                newest = max(
                    [streams.stat().st_mtime]
                    + [f.stat().st_mtime for f in streams.iterdir()]
                )
            except OSError:
                continue
            if newest > cutoff:
                continue
        try:
            shutil.rmtree(streams)
        except OSError:
            continue
        removed.append(streams)
    return removed


def in_flight_path(repo_root: Path, slug: str) -> Path:
    """Return the in-flight snapshot path for a slug.

    One snapshot per slug — last writer wins on every *write*. Callers
    re-running ``plan-tool`` against the same plan overwrite this file;
    that's acceptable and matches the concurrency stance in
    ``checkpoint.py``. Teardown (``RunLogWriter.run_end``) is a guarded
    delete rather than an unconditional one: it skips the unlink when a
    newer same-slug run's ``run_id`` is on disk, so a completing call
    can't erase a still-running sibling's snapshot out from under it.
    """
    return run_dir(repo_root, slug) / IN_FLIGHT_FILENAME


@contextmanager
def _in_flight_snapshot_guard(path: Path) -> Iterator[None]:
    """Serialize a slug's snapshot replacement and guarded removal."""
    key = path.resolve()
    with _IN_FLIGHT_GUARDS_LOCK:
        local_lock = _IN_FLIGHT_GUARDS.setdefault(key, threading.Lock())

    with local_lock:
        lock_path = Path(f"{path}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        implementation: Optional[str] = None
        try:
            if _fcntl is not None:
                _fcntl.flock(descriptor, _fcntl.LOCK_EX)
                implementation = "fcntl"
            elif _msvcrt is not None:  # pragma: no cover - Windows only.
                if os.fstat(descriptor).st_size < 1:
                    os.ftruncate(descriptor, 1)
                os.lseek(descriptor, 0, os.SEEK_SET)
                _msvcrt.locking(descriptor, _msvcrt.LK_LOCK, 1)
                implementation = "msvcrt"
            yield
        finally:
            if implementation == "fcntl" and _fcntl is not None:
                _fcntl.flock(descriptor, _fcntl.LOCK_UN)
            elif implementation == "msvcrt" and _msvcrt is not None:
                os.lseek(descriptor, 0, os.SEEK_SET)
                _msvcrt.locking(descriptor, _msvcrt.LK_UNLCK, 1)
            os.close(descriptor)


# ---------- timestamps and run ids ----------


def utc_now_iso() -> str:
    """ISO-8601 UTC seconds-precision timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    """Return an ID safe to use as a filename component.

    Format: ``<UTC ISO with colons replaced by dashes>-<6 hex chars>``,
    e.g. ``2026-05-14T12-34-56+00-00-9f3a1c``. The hex tail comes from
    ``secrets.token_hex(3)`` so two runs started in the same second
    don't collide.
    """
    ts = utc_now_iso().replace(":", "-")
    return f"{ts}-{secrets.token_hex(3)}"


# ---------- I/O primitives ----------


class RunLogLineTooLarge(ValueError):
    """Raised when a single event exceeds ``_MAX_LINE_BYTES``."""


def _truncate_long_strings(value: Any, *, max_len: int = _MAX_STRING_LEN_IN_PAYLOAD) -> Any:
    """Recursively walk ``value``; truncate any string longer than
    ``max_len`` with a visible elision marker.

    Used to keep one oversized field (typically ``argv`` containing a
    long ``--from`` description) from blowing the ``_MAX_LINE_BYTES``
    cap. Truncation is best-effort: pathological payloads with many
    medium-sized strings can still exceed the cap and trigger
    ``RunLogLineTooLarge``. Dicts and lists are walked recursively;
    other types are returned unchanged.

    The elision marker (``…<elided N chars>``) is inline so
    ``plan-tool runs show`` makes it obvious the event was abridged
    rather than silently losing tail bytes.
    """
    if isinstance(value, str):
        if len(value) > max_len:
            head_len = max(0, max_len - _ELISION_RESERVED)
            head = value[:head_len]
            elided = len(value) - head_len
            return f"{head}…<elided {elided} chars>"
        return value
    if isinstance(value, dict):
        return {k: _truncate_long_strings(v, max_len=max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_long_strings(v, max_len=max_len) for v in value]
    if isinstance(value, tuple):
        return tuple(_truncate_long_strings(v, max_len=max_len) for v in value)
    return value


def _bounded_violations(messages: Sequence[str]) -> tuple[list[str], int]:
    """Whole messages fitting ``_MAX_VIOLATION_BYTES_IN_PAYLOAD``, and the
    number dropped.

    The first message is kept whatever its size: an oversized one is elided
    visibly by :func:`_truncate_long_strings`, which beats an event that
    reports violations while showing none. Shared by every event carrying a
    bounded list — the budget is a byte figure, not a claim about messages.
    """
    kept: list[str] = []
    used = 0
    for message in messages:
        # Serialized, not raw: escaping is what lands on the line, and a
        # quote-heavy message costs about twice its character count.
        cost = len(json.dumps(message, ensure_ascii=False).encode("utf-8"))
        if kept and used + cost > _MAX_VIOLATION_BYTES_IN_PAYLOAD:
            break
        kept.append(message)
        used += cost
    return kept, len(messages) - len(kept)


def _append_jsonl_line(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON-serialized dict as a single line to ``path``.

    Creates ``path.parent`` if absent. Uses ``os.open`` +
    ``os.write`` (rather than a buffered file object) so the
    ``O_APPEND`` atomicity guarantee from POSIX ``write(2)`` applies
    per call.

    Before serialization, any individual string longer than
    ``_MAX_STRING_LEN_IN_PAYLOAD`` is truncated with an elision marker
    (see :func:`_truncate_long_strings`). The original failure mode
    -- ``argv`` containing a long ``--from`` description -- is fixed
    this way: the long string is bounded, and the resulting line fits
    under ``_MAX_LINE_BYTES``. Pathological payloads (many
    medium-sized strings whose sum still exceeds the cap) raise
    ``RunLogLineTooLarge``; the file is not modified in that case.
    """
    payload = _truncate_long_strings(payload)
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = line.encode("utf-8") + b"\n"
    if len(encoded) > _MAX_LINE_BYTES:
        raise RunLogLineTooLarge(f"event line is {len(encoded)} bytes (cap {_MAX_LINE_BYTES})")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Held only around the file write so concurrent worker threads (detail's
    # ``jobs > 1`` pool) can't tear a line; see ``_APPEND_LOCK``.
    with _APPEND_LOCK:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)


# ``claude_call_end`` fields summed into ``run_end.usage``.
_USAGE_FIELDS = (
    "tokens_input",
    "tokens_output",
    "cache_creation_tokens",
    "cache_read_tokens",
    "cost_usd",
)


def _make_call_end_sink(
    *,
    run_id: str,
    log_path: Path,
    phase: str,
    attempt: int,
    context_getter: Optional[Callable[[], dict[str, Any]]] = None,
    on_event: Optional[Callable[[ClaudeCallEnd], None]] = None,
) -> "Callable[[ClaudeCallEnd], None]":
    """Build the shell sink shared by both installers.

    Rewrites the event's empty ``run_id`` and substitutes the caller's
    ``phase``/``attempt`` — see :meth:`RunLogWriter.bind_shell_sink` for
    why that override is load-bearing. The installers differ in lifecycle
    (scoped context manager vs. stateful install/uninstall), not in what
    the sink writes.
    """

    def _sink(event: ClaudeCallEnd) -> None:
        payload = asdict(event)
        payload["run_id"] = run_id
        payload["phase"] = phase
        payload["attempt"] = attempt
        if context_getter is not None:
            for key, value in context_getter().items():
                payload.setdefault(key, value)
        # Count before the write: a failed log append must not drop the call
        # from the run's totals.
        if on_event is not None:
            on_event(event)
        _append_jsonl_line(log_path, payload)

    return _sink


def hash_prompt(prompt: str) -> str:
    """Hex SHA-256 of *prompt* for ``claude_call_start.prompt_sha256``."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def append_event(path: Path, event: Event) -> None:
    """Append one JSON-encoded event as a single line to ``path``.

    See :func:`_append_jsonl_line` for the atomicity guarantees and
    size-cap semantics. Callers wanting to attach extra ad-hoc fields
    (``step_id``, ``cached``, ``error``, ...) without growing every
    event dataclass should use :class:`RunLogWriter` instead — its
    emit helpers merge ``**extra`` kwargs into the serialized payload.
    """
    _append_jsonl_line(path, asdict(event))


def write_in_flight(path: Path, snapshot: dict[str, Any]) -> None:
    """Atomically replace the in-flight snapshot at ``path``.

    Writes a sibling tempfile in the same directory and ``os.replace``s
    it into place. A crash mid-write leaves the previous snapshot
    intact (or nothing, if this is the first write). Same pattern as
    ``checkpoint.save_checkpoint``.

    ``snapshot`` is a dict because callers compose ad-hoc shapes —
    typically ``{"schema_version": 1, "run_id": ..., "current_phase":
    ..., "started_at": ..., "last_event_ts": ...}``. Pinning a
    dataclass here would force every caller's snapshot through one
    type; humans ``cat``ing this file with ``jq`` should see exactly
    what the caller wrote.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_in_flight(path: Path) -> Optional[dict[str, Any]]:
    """Return the in-flight snapshot or ``None`` if missing/garbage.

    Returns ``None`` on a missing file, unreadable bytes, malformed
    JSON, a non-dict top-level value, or a ``schema_version`` that
    doesn't match ``RUN_LOG_SCHEMA_VERSION``. Same fail-safe contract
    as ``checkpoint.load_if_valid`` — callers treat ``None`` as "no
    in-flight run".
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("schema_version") != RUN_LOG_SCHEMA_VERSION:
        return None
    return obj


@dataclass(frozen=True)
class RunOutcome:
    """Terminal summary of the readable events in one run log."""

    run_id: str
    completed: bool
    outcome: str = ""
    rc: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    iteration_outcomes: dict[int, str] = field(default_factory=dict)


def read_run_events(path: Path) -> list[dict[str, Any]]:
    """Return readable JSON-object events from a completed run log.

    Each damaged, blank, or non-object line is skipped independently so a
    truncated final append does not hide earlier events. Schema versions and
    event discriminators are intentionally left uninterpreted.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []

    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def read_run_outcome(path: Path) -> Optional[RunOutcome]:
    """Summarize a run log, or return ``None`` when it has no events."""
    events = read_run_events(path)
    if not events:
        return None

    run_end = next(
        (event for event in reversed(events) if event.get("event") == "run_end"),
        None,
    )
    iteration_outcomes = {
        event["step_id"]: event["outcome"]
        for event in events
        if event.get("event") == "iteration_end"
        and isinstance(event.get("step_id"), int)
        and isinstance(event.get("outcome"), str)
    }
    if run_end is None:
        first_run_id = events[0].get("run_id")
        return RunOutcome(
            run_id=first_run_id if isinstance(first_run_id, str) else "",
            completed=False,
            iteration_outcomes=iteration_outcomes,
        )

    run_id = run_end.get("run_id")
    outcome = run_end.get("outcome")
    rc = run_end.get("rc")
    duration_ms = run_end.get("duration_ms")
    error = run_end.get("error")
    return RunOutcome(
        run_id=run_id if isinstance(run_id, str) else "",
        completed=True,
        outcome=outcome if isinstance(outcome, str) else "",
        rc=rc if isinstance(rc, int) else 0,
        duration_ms=duration_ms if isinstance(duration_ms, int) else 0,
        error=error if isinstance(error, str) else None,
        iteration_outcomes=iteration_outcomes,
    )


# ---------- writer ----------


@runtime_checkable
class RunnerObserver(Protocol):
    """Structural contract ``backend_runner.run_streaming_once`` calls for
    the spawn / stream / progress / stall / termination / interrupt signals
    of one backend child process.

    Method names and keyword-only signatures mirror the matching
    :class:`RunLogWriter` methods exactly, so a real ``RunLogWriter``
    satisfies this Protocol with zero adaptation. ``backend_runner`` calls
    every method uniformly through ``getattr`` (see ``_safe_observer_call``)
    with no ``isinstance`` distinction — a bare ``RunLogWriter`` and a
    purpose-built observer (see ``shell.claude_invoke``) both get
    ``run_interrupted`` calls forwarded the same way.
    """

    def backend_spawn(
        self,
        *,
        phase: str,
        attempt: int,
        backend: str,
        transport: Optional[str] = None,
        child_pid: Optional[int] = None,
        effective_timeout_ms: Optional[int] = None,
        prompt_bytes: Optional[int] = None,
        stream_log: Optional[str] = None,
        **extra: Any,
    ) -> None: ...

    def backend_termination(
        self,
        *,
        phase: str,
        attempt: int,
        backend: str,
        reason: str,
        duration_ms: int,
        signal_or_timeout: Optional[str] = None,
        silent_ms: Optional[int] = None,
        **extra: Any,
    ) -> None: ...

    def claude_stream_event(
        self,
        *,
        phase: str,
        attempt: int,
        kind: str,
        tool_name: Optional[str] = None,
        tool_input_summary: Optional[str] = None,
        bytes_in_delta: int = 0,
        **extra: Any,
    ) -> None: ...

    def claude_call_progress(
        self,
        *,
        phase: str,
        attempt: int,
        elapsed_ms: int,
        silent_ms: int,
        last_tool: Optional[str] = None,
        last_activity_kind: Optional[str] = None,
        **extra: Any,
    ) -> None: ...

    def claude_call_stall_suspected(
        self,
        *,
        phase: str,
        attempt: int,
        silent_ms: int,
        threshold_ms: int,
        last_tool: Optional[str] = None,
        **extra: Any,
    ) -> None: ...

    def run_interrupted(
        self,
        *,
        phase: str,
        attempt: int,
        source: str,
        signal: str = "SIGINT",
        **extra: Any,
    ) -> None: ...


class RunLogWriter:
    """Per-invocation handle that emits structured events to one JSONL log.

    Constructed via :meth:`start`, which writes the ``run_start`` event
    plus the initial in-flight snapshot atomically before returning.
    Callers then call :meth:`phase_start` / :meth:`phase_end` /
    :meth:`claude_call_start` / :meth:`bind_shell_sink` around the work
    they want to time, and :meth:`run_end` once from a single ``finally:``
    covering every return path so the snapshot file is cleaned up.

    The writer owns one ``run_id`` and one JSONL path for its lifetime;
    a single ``plan-tool`` invocation always opens at most one writer.

    The emit helpers each accept ``**extra`` keyword arguments that are
    merged into the JSON payload alongside the dataclass fields. That
    lets callers attach ad-hoc context (``step_id``, ``attempt``,
    ``cached``, ``rc``, ``error``, ...) without forcing every event
    dataclass to grow a new field; the dataclass schema in this module
    stays the strict union of *required* fields.
    """

    __slots__ = (
        "repo_root",
        "slug",
        "run_id",
        "log_path",
        "in_flight_path",
        "_started_monotonic",
        # Stack of prior shell sinks captured by
        # ``install_call_end_sink``. A stack (rather than a single slot)
        # so nested install/uninstall pairs survive without clobbering
        # the outer binding's restore target — useful when a caller
        # threads the writer through a callee that *also* installs its
        # own sink (e.g. a future iteration loop wrapping
        # ``propose_steps_from_claude``).
        "_prev_shell_sinks",
        # Parallel stack to ``_prev_shell_sinks``, restoring
        # ``shell.py``'s writer ``ContextVar`` in the same LIFO order —
        # always pushed/popped together by ``install_call_end_sink`` /
        # ``uninstall_call_end_sink``.
        "_prev_run_loggers",
        # Most recent reason recorded by ``backend_termination`` /
        # ``run_interrupted`` on this writer. ``run_end`` reads this when
        # its own ``termination_reason`` argument is absent. Plain
        # last-write-wins already gives "interrupt wins" precedence: a
        # ``run_interrupted`` call always re-raises the interrupt it
        # observed, so nothing else in a plan-tool invocation runs
        # afterward to overwrite it.
        "_last_termination_reason",
        # Running per-field usage over this run's ``claude_call_end`` events,
        # summed into ``run_end.usage``; guarded by ``_usage_lock`` because
        # parallel workers share one writer.
        "_usage",
        "_usage_lock",
        # The in-flight snapshot dict this writer owns, seeded by
        # ``start()`` and merged into (never rebuilt) by every
        # ``_refresh_in_flight`` call — see that method for why merging
        # is what keeps every write a valid, fully-populated snapshot.
        "_in_flight_snapshot",
        # The copied optional context envelope. Its ``command`` field is
        # initialized by ``start()`` and remains writer-owned thereafter.
        "_context",
        # Context keys that were flattened into the initial snapshot. This
        # lets a replacement remove stale context without touching snapshot
        # identity or lifecycle fields that happened to share a name.
        "_snapshot_context_keys",
        # Serializes ``_refresh_in_flight``'s merge-then-write against
        # concurrent callers on this writer (the heartbeat daemon thread
        # vs. the phase/backend-lifecycle calls on the main thread).
        # Separate from the module-level ``_APPEND_LOCK``, which guards
        # only the JSONL append.
        "_in_flight_lock",
    )

    def __init__(
        self,
        *,
        repo_root: Path,
        slug: str,
        run_id: str,
        log_path: Path,
        in_flight_path: Path,
        started_monotonic: float,
        context: Optional[Mapping[str, Any]],
    ) -> None:
        self.repo_root = repo_root
        self.slug = slug
        self.run_id = run_id
        self.log_path = log_path
        self.in_flight_path = in_flight_path
        self._started_monotonic = started_monotonic
        self._prev_shell_sinks: list = []
        self._prev_run_loggers: list = []
        self._last_termination_reason: Optional[str] = None
        self._usage: dict[str, Any] = {"calls": 0, **{f: [0, 0] for f in _USAGE_FIELDS}}
        self._usage_lock = threading.Lock()
        self._in_flight_snapshot: dict[str, Any] = {}
        self._context = dict(context) if context is not None else None
        self._snapshot_context_keys: set[str] = set()
        self._in_flight_lock = threading.Lock()

    @classmethod
    def start(
        cls,
        *,
        repo_root: Path,
        slug: str,
        command: str,
        argv: list[str],
        plan_path: Optional[Path] = None,
        step_filter: Optional[int] = None,
        flags: Optional[dict[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> "RunLogWriter":
        """Open a fresh run log and emit ``run_start`` + in-flight snapshot.

        ``slug`` namespaces the log file under
        ``<repo_root>/.plan-tool/runs/<slug>/<run_id>.jsonl``; pick the
        same slug callers already use for ``save_review`` (typically
        ``args.name``) so per-plan tooling can scan one directory.
        ``flags`` is a bounded dict of caller-relevant booleans/values
        (``mode``, ``dry_run``, ``no_walk``...) — keep it small so the
        ``run_start`` line stays under the per-line size cap.

        ``context`` is an optional flat envelope that follows every writer
        event and in-flight snapshot. The writer copies it, owns subsequent
        updates, and keeps the command passed here authoritative.
        """
        if context is not None:
            _validate_context_values(context)
        run_id = new_run_id()
        log_path = run_log_path(repo_root, slug, run_id)
        ifp = in_flight_path(repo_root, slug)
        started_at = utc_now_iso()
        started_monotonic = time.monotonic()

        writer = cls(
            repo_root=repo_root,
            slug=slug,
            run_id=run_id,
            log_path=log_path,
            in_flight_path=ifp,
            started_monotonic=started_monotonic,
            context=(
                {
                    **{
                        key: value
                        for key, value in context.items()
                        if key not in _CONTEXT_RESERVED_KEYS
                    },
                    "command": command,
                }
                if context is not None
                else None
            ),
        )

        run_start_payload: dict[str, Any] = {
            "ts": started_at,
            "run_id": run_id,
            "event": "run_start",
            "schema_version": RUN_LOG_SCHEMA_VERSION,
            "command": command,
            "plan_slug": slug,
            "argv": list(argv),
            "pid": os.getpid(),
            "cwd": os.getcwd(),
        }
        if plan_path is not None:
            run_start_payload["plan_path"] = str(plan_path)
        if step_filter is not None:
            run_start_payload["step_filter"] = step_filter
        if flags:
            run_start_payload["flags"] = dict(flags)
        writer._add_context_to_payload(run_start_payload)
        _append_jsonl_line(log_path, run_start_payload)

        snapshot: dict[str, Any] = {
            "schema_version": RUN_LOG_SCHEMA_VERSION,
            "run_id": run_id,
            "command": command,
            "plan_slug": slug,
            "started_at": started_at,
            "log_path": str(log_path),
            "status": IN_FLIGHT_STATUS_RUNNING,
        }
        if plan_path is not None:
            snapshot["plan_path"] = str(plan_path)
        if step_filter is not None:
            snapshot["step_filter"] = step_filter
        if flags:
            snapshot["flags"] = dict(flags)
        writer._snapshot_context_keys = writer._add_context_to_payload(snapshot)
        with _in_flight_snapshot_guard(ifp):
            write_in_flight(ifp, snapshot)
        writer._in_flight_snapshot = snapshot

        return writer

    # ---- emit helpers ----

    @property
    def has_context(self) -> bool:
        """Whether this writer was opened with the optional context envelope.

        Lets a caller check the precondition :meth:`update_context` enforces
        without relying on catching its ``RuntimeError``.
        """
        return self._context is not None

    def _current_context(self) -> dict[str, Any]:
        """Return one stable copy of the optional writer-owned envelope."""
        with self._in_flight_lock:
            return dict(self._context) if self._context is not None else {}

    def _add_context_to_payload(self, payload: dict[str, Any]) -> set[str]:
        """Flatten context fields that do not collide with ``payload``."""
        added: set[str] = set()
        for key, value in self._current_context().items():
            if key not in payload:
                payload[key] = value
                added.add(key)
        return added

    def update_context(self, **fields: Any) -> None:
        """Merge ``fields`` into context, then immediately republish the snapshot."""
        _validate_context_values(fields)
        with self._in_flight_lock:
            if self._context is None:
                raise RuntimeError("cannot update a writer without context")

            next_context = dict(self._context)
            next_context.update(
                {key: value for key, value in fields.items() if key not in _CONTEXT_RESERVED_KEYS}
            )
            next_context["command"] = self._context["command"]

            old_snapshot_keys = self._snapshot_context_keys
            self._context = next_context
            self._snapshot_context_keys = set()
            for key in old_snapshot_keys - next_context.keys():
                self._in_flight_snapshot.pop(key, None)
            for key, value in next_context.items():
                if key in old_snapshot_keys:
                    self._in_flight_snapshot[key] = value
                    self._snapshot_context_keys.add(key)
                elif key not in self._in_flight_snapshot:
                    self._in_flight_snapshot[key] = value
                    self._snapshot_context_keys.add(key)
            self._persist_in_flight_locked()

    def _emit(self, event: Event, **extra: Any) -> None:
        # Writers that emit call ends themselves (roadmap materialization) reach
        # the totals here; the shell sink path counts via ``on_event`` instead.
        if isinstance(event, ClaudeCallEnd):
            self._record_usage(event)
        payload = asdict(event)
        # ``event`` isn't always a registered ``_BaseEvent`` subclass — a
        # producer-local redaction dataclass (e.g. roadmap.py's
        # ``_RedactedClaudeStreamEvent``) can duck-type its way in here too,
        # so this can't assume the attribute exists.
        for field_name in getattr(event, "omit_when_none", frozenset()):
            if payload.get(field_name) is None:
                payload.pop(field_name, None)
        context = self._current_context()
        for key, value in context.items():
            payload.setdefault(key, value)
        if extra:
            # Context is the authoritative source for anything it tracks —
            # a caller wanting an event to reflect a new context-tracked
            # value calls `update_context()` first rather than passing an
            # `extra` override, so `extra` only fills fields context leaves
            # untouched. See `test_context_is_copied_and_cannot_override_
            # event_identity`, which pins this for both the reserved
            # `command` field and an ordinary context field.
            payload.update((key, value) for key, value in extra.items() if key not in context)
        _append_jsonl_line(self.log_path, payload)

    def _persist_in_flight_locked(self) -> None:
        """Stamp and best-effort write the held snapshot. Caller holds the lock.

        Best-effort: a broken snapshot write must not fail the run or kill
        the heartbeat daemon, matching :meth:`run_end`'s unlink stance.
        """
        self._in_flight_snapshot["last_event_ts"] = utc_now_iso()
        try:
            with _in_flight_snapshot_guard(self.in_flight_path):
                on_disk = read_in_flight(self.in_flight_path)
                if on_disk is not None and on_disk.get("run_id") != self.run_id:
                    return
                write_in_flight(self.in_flight_path, self._in_flight_snapshot)
        except OSError:
            pass

    def _refresh_in_flight(self, **updates: Any) -> None:
        """Merge ``updates`` into the held in-flight snapshot and write it.

        Merging (never rebuilding from scratch) is what guarantees every
        refresh still carries ``schema_version``/``run_id``/``command``/
        ``plan_slug``/``started_at``/``log_path`` from :meth:`start`, so
        :func:`read_in_flight` keeps accepting the file after any refresh.
        The lock serializes merge+write pairs across threads — the
        heartbeat daemon thread calls this via :meth:`claude_call_progress`
        while phase/backend-lifecycle calls happen elsewhere — so a late
        heartbeat can only ever re-emit the current ``status`` with fresher
        timing fields, never overwrite a newer status with a stale one.
        """
        with self._in_flight_lock:
            context = self._context or {}
            self._in_flight_snapshot.update(
                (key, value) for key, value in updates.items() if key not in context
            )
            self._persist_in_flight_locked()

    def phase_start(self, phase: str, **extra: Any) -> None:
        ev = PhaseStart(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
        )
        self._emit(ev, **extra)
        self._refresh_in_flight(current_phase=phase, status=IN_FLIGHT_STATUS_RUNNING)

    def phase_end(
        self,
        phase: str,
        duration_ms: int,
        outcome: str,
        **extra: Any,
    ) -> None:
        """Emit ``phase_end``. Positional args match the ``_RunLogger``
        legacy signature ``create.py`` was written against; keyword
        form is still supported for callers (``cmd_detail``,
        ``cmd_run``) that prefer it.
        """
        ev = PhaseEnd(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            duration_ms=duration_ms,
            outcome=outcome,
        )
        self._emit(ev, **extra)

    def claude_call_start(
        self,
        phase: str,
        attempt: int,
        prompt_bytes: int,
        prompt_sha256: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Emit ``claude_call_start``. Positional args match the
        ``_ClaudeCallStartSink`` Protocol in ``progress.py`` so a
        :class:`RunLogWriter` can be passed directly as a reporter tee
        via ``StderrReporter(run_log=writer)``; keyword form is still
        supported for callers (``cmd_run``, ``cmd_detail``) that
        prefer it.
        """
        ev = ClaudeCallStart(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            prompt_bytes=prompt_bytes,
            prompt_sha256=prompt_sha256,
        )
        self._emit(ev, **extra)

    def attempt_failed(
        self,
        *,
        phase: str,
        attempt: int,
        failure_kind: str,
        **extra: Any,
    ) -> None:
        """Emit one ``attempt_failed`` event — which kind consumed an attempt.

        Call it once per failed attempt for **every** failure kind, including
        the gates kind that also emits ``gate_violations``, and including the
        attempt that spends the budget. An attempt that fails and then
        recovers is otherwise invisible: the result carries only the
        successful run. See `DATA_CONTRACT.md`.
        """
        ev = AttemptFailed(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            failure_kind=failure_kind,
        )
        self._emit(ev, **extra)

    def model_failure_receipt(
        self,
        *,
        phase: str,
        attempt: int,
        reason: str,
        response_bytes: Optional[int],
        response_sha256: Optional[str],
        sidecar_result: ModelResponseSidecarResult,
    ) -> None:
        """Emit a redacted rejected-response receipt after sidecar storage."""
        if response_bytes is not None and response_bytes < 0:
            raise ValueError("response_bytes must be non-negative")
        if response_bytes is None:
            response_sha256 = None
            sidecar_disposition = "no-response"
            sidecar_path = None
        else:
            if response_sha256 is None or not _ROADMAP_ESCALATION_SHA256_RE.fullmatch(
                response_sha256
            ):
                raise ValueError("response_sha256 must be a SHA-256 digest when response bytes exist")
            sidecar_disposition = sidecar_result.outcome.value
            sidecar_path = None
            if sidecar_disposition == "written" and sidecar_result.path is not None:
                try:
                    sidecar_path = str(sidecar_result.path.relative_to(self.repo_root))
                except ValueError:
                    raise ValueError("written sidecar path must be beneath repo_root") from None
        ev = ModelFailureReceipt(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            reason=reason,
            response_bytes=response_bytes,
            response_sha256=response_sha256,
            sidecar_disposition=sidecar_disposition,
            sidecar_path=sidecar_path,
        )
        self._emit(ev)

    def gate_violations(
        self,
        *,
        phase: str,
        attempt: int,
        messages: Sequence[str],
        **extra: Any,
    ) -> None:
        """Emit one ``gate_violations`` event — what consumed a failed attempt.

        ``phase_end`` records only ``ok`` / ``exhausted``, so without this a
        stage that passed on its last attempt is indistinguishable from a
        clean first-try pass. Call it once per attempt whose gates rejected
        the artifact, including the attempt that spends the budget.
        """
        kept, omitted = _bounded_violations(messages)
        ev = GateViolations(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            violation_count=len(messages),
            violations=kept,
            violations_omitted=omitted,
        )
        self._emit(ev, **extra)

    def backend_spawn(
        self,
        *,
        phase: str,
        attempt: int,
        backend: str,
        transport: Optional[str] = None,
        child_pid: Optional[int] = None,
        effective_timeout_ms: Optional[int] = None,
        prompt_bytes: Optional[int] = None,
        stream_log: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Emit one ``backend_spawn`` event — a backend child is about to run."""
        ev = BackendSpawn(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            backend=backend,
            transport=transport,
            child_pid=child_pid,
            effective_timeout_ms=effective_timeout_ms,
            prompt_bytes=prompt_bytes,
            stream_log=stream_log,
        )
        self._emit(ev, **extra)
        self._refresh_in_flight(
            status=IN_FLIGHT_STATUS_RUNNING,
            child_pid=child_pid,
            effective_timeout_ms=effective_timeout_ms,
            transport=transport,
            prompt_bytes=prompt_bytes,
        )

    def backend_termination(
        self,
        *,
        phase: str,
        attempt: int,
        backend: str,
        reason: str,
        duration_ms: int,
        signal_or_timeout: Optional[str] = None,
        silent_ms: Optional[int] = None,
        **extra: Any,
    ) -> None:
        """Emit one ``backend_termination`` event and track ``reason`` as
        this writer's most recent termination reason.

        :meth:`run_end` reads the tracked value when its own
        ``termination_reason`` argument is absent — see that method.
        """
        ev = BackendTermination(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            backend=backend,
            reason=reason,
            duration_ms=duration_ms,
            signal_or_timeout=signal_or_timeout,
            silent_ms=silent_ms,
        )
        self._emit(ev, **extra)
        self._last_termination_reason = reason
        self._refresh_in_flight(status=IN_FLIGHT_STATUS_TERMINATED, termination_reason=reason)

    def run_interrupted(
        self,
        *,
        phase: str,
        attempt: int,
        source: str,
        signal: str = "SIGINT",
        **extra: Any,
    ) -> None:
        """Emit one ``run_interrupted`` event and mark this writer's
        tracked termination reason ``"operator_interrupt"``.

        Always wins over an earlier ``backend_termination`` on the same
        writer: a ``run_interrupted`` call re-raises the interrupt it
        observed, so nothing else in the invocation runs afterward to
        overwrite the tracked value.
        """
        ev = RunInterrupted(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            source=source,
            signal=signal,
        )
        self._emit(ev, **extra)
        self._last_termination_reason = "operator_interrupt"

    def reset_termination_reason(self) -> None:
        """Clear the tracked last termination reason.

        A multi-row batch command (roadmap seed materialize/refresh) reuses
        one writer across several independent per-row backend lineages.
        Without a reset, whichever row's ``backend_termination`` happened to
        run last decides what :meth:`run_end` reports for the *whole*
        command — which can misrepresent a "partial"/"exhausted" batch as
        cleanly "completed" if the last row to run happened to succeed.
        Call this once after a multi-row loop finishes so ``run_end`` omits
        the field rather than reporting a reason that belongs to only one
        row of a mixed batch.
        """
        self._last_termination_reason = None

    def backend_recovery_wait(
        self,
        *,
        phase: str,
        attempt: int,
        reason: str,
        delay_ms: int,
        next_attempt: int,
        backend: str,
        **extra: Any,
    ) -> None:
        """Emit one ``backend_recovery_wait`` event.

        Marks that the shared rate-limit/transient recovery loop
        (``rate_limit_loop.run_with_rate_limit_recovery``) is
        intentionally sleeping between attempts, not hung.
        """
        ev = BackendRecoveryWait(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            reason=reason,
            delay_ms=delay_ms,
            next_attempt=next_attempt,
            backend=backend,
        )
        self._emit(ev, **extra)
        self._refresh_in_flight(
            status=IN_FLIGHT_STATUS_AWAITING_RETRY,
            recovery_reason=reason,
            recovery_delay_ms=delay_ms,
            recovery_next_attempt=next_attempt,
        )

    def roadmap_preflight_failed(self, *, check: str) -> None:
        """Emit one typed roadmap pre-flight failure without error prose."""
        ev = RoadmapPreflightFailed(
            ts=utc_now_iso(),
            run_id=self.run_id,
            check=check,
        )
        self._emit(ev)

    def roadmap_stage_written(
        self,
        *,
        phase: str,
        stage: int,
        artifact_path: str,
        artifact_digest: str,
        replaced: bool,
        draft_seed_count: int,
    ) -> None:
        """Emit one accepted roadmap artifact write and its side-output count."""
        ev = RoadmapStageWritten(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            stage=stage,
            artifact_path=artifact_path,
            artifact_digest=artifact_digest,
            replaced=replaced,
            draft_seed_count=draft_seed_count,
        )
        self._emit(ev)

    def roadmap_seed_apply_result(
        self,
        *,
        outcome: str,
        target_count: int,
        promotion_count: int,
        collision_count: int,
        missing_draft_count: int,
        malformed_draft_count: int,
        stale_draft_count: int,
        path_escaping_draft_count: int,
        duplicate_draft_count: int,
        digest_mismatched_draft_count: int,
    ) -> None:
        """Emit the aggregate outcome of one apply-only seed promotion."""
        ev = RoadmapSeedApplyResult(
            ts=utc_now_iso(),
            run_id=self.run_id,
            outcome=outcome,
            target_count=target_count,
            promotion_count=promotion_count,
            collision_count=collision_count,
            missing_draft_count=missing_draft_count,
            malformed_draft_count=malformed_draft_count,
            stale_draft_count=stale_draft_count,
            path_escaping_draft_count=path_escaping_draft_count,
            duplicate_draft_count=duplicate_draft_count,
            digest_mismatched_draft_count=digest_mismatched_draft_count,
        )
        self._emit(ev)

    def roadmap_structural_revision_preflight(
        self,
        *,
        receipt_final: Optional[str],
        analysis_final: Optional[str],
        artifact_key: Optional[str],
        feedback_id: Optional[str],
        target_row_id: Optional[str],
        binding_digest: Optional[str],
        render_canonical: Optional[bool],
        verdict: str,
    ) -> None:
        """Emit one closed structural-revision admission result."""
        if verdict not in {
            "mode-rejected",
            "evaluator-rejected",
            "evidence-rejected",
            "changed-brief",
            "legacy-brief",
            "feedback-rejected",
            "render-canonical-rejected",
            "enrolled-roadmap-rejected",
            "accepted",
            "interrupted",
        }:
            raise ValueError(f"invalid structural revision preflight verdict: {verdict!r}")
        _validate_roadmap_structural_revision_preflight_facts(
            receipt_final=receipt_final,
            analysis_final=analysis_final,
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            target_row_id=target_row_id,
            binding_digest=binding_digest,
            render_canonical=render_canonical,
            verdict=verdict,
        )
        ev = RoadmapStructuralRevisionPreflight(
            ts=utc_now_iso(),
            run_id=self.run_id,
            receipt_final=receipt_final,
            analysis_final=analysis_final,
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            target_row_id=target_row_id,
            binding_digest=binding_digest,
            render_canonical=render_canonical,
            verdict=verdict,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def roadmap_structural_revision_attempt(
        self,
        *,
        attempt: int,
        binding_digest: str,
        invalidated_seed_count: Optional[int],
        operation_verdict: str,
        merge_verdict: str,
        proof_verdict: str,
        final_snapshot_verdict: str,
        publication_outcome: str,
        outcome: str,
    ) -> None:
        """Emit one closed terminal structural-revision attempt."""
        _validate_roadmap_structural_revision_attempt(
            attempt=attempt,
            binding_digest=binding_digest,
            invalidated_seed_count=invalidated_seed_count,
            operation_verdict=operation_verdict,
            merge_verdict=merge_verdict,
            proof_verdict=proof_verdict,
            final_snapshot_verdict=final_snapshot_verdict,
            publication_outcome=publication_outcome,
            outcome=outcome,
        )
        ev = RoadmapStructuralRevisionAttempt(
            ts=utc_now_iso(),
            run_id=self.run_id,
            attempt=attempt,  # type: ignore[arg-type]
            binding_digest=binding_digest,
            invalidated_seed_count=invalidated_seed_count,
            operation_verdict=operation_verdict,  # type: ignore[arg-type]
            merge_verdict=merge_verdict,  # type: ignore[arg-type]
            proof_verdict=proof_verdict,  # type: ignore[arg-type]
            final_snapshot_verdict=final_snapshot_verdict,  # type: ignore[arg-type]
            publication_outcome=publication_outcome,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def roadmap_escalation_preflight(
        self,
        *,
        artifact_key: Optional[str],
        feedback_id: Optional[str],
        reason: Optional[str],
        target_kind: Optional[str],
        target_id: Optional[str],
        artifact_digest: Optional[str],
        verdict: str,
    ) -> None:
        """Emit one closed receipt preflight without an extension bag."""
        if verdict not in {
            "mode-rejected",
            "malformed-selector",
            "unknown-artifact",
            "identifier-rejected",
            "reason-rejected",
            "artifact-unreadable",
            "artifact-unparsable",
            "artifact-not-current",
            "missing-feedback",
            "duplicate-feedback",
            "not-open",
            "already-responded",
            "missing-or-ambiguous-target",
            "target-not-live-in-selected-artifact",
            "accepted",
            "interrupted",
        }:
            raise ValueError(f"invalid roadmap escalation preflight verdict: {verdict!r}")
        # Same hand-copied vocabulary as RoadmapEscalationPreflight.reason
        # above, for the same leaf-module dependency-isolation reason.
        if reason is not None and reason not in {
            "prose",
            "row-structure",
            "collection-structure",
            "relationship-semantics",
            "decision-semantics",
            "cross-artifact-impact",
        }:
            raise ValueError(f"invalid roadmap escalation reason: {reason!r}")
        if target_kind is not None and target_kind not in {"artifact", "row"}:
            raise ValueError(f"invalid roadmap escalation target kind: {target_kind!r}")
        _validate_roadmap_escalation_preflight_facts(
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            reason=reason,
            target_kind=target_kind,
            target_id=target_id,
            artifact_digest=artifact_digest,
            verdict=verdict,
        )
        ev = RoadmapEscalationPreflight(
            ts=utc_now_iso(),
            run_id=self.run_id,
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            reason=reason,  # type: ignore[arg-type]
            target_kind=target_kind,  # type: ignore[arg-type]
            target_id=target_id,
            artifact_digest=artifact_digest,
            verdict=verdict,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def roadmap_escalation_result(
        self,
        *,
        outcome: str,
        receipt_id: Optional[str],
        handoff: Optional[str],
    ) -> None:
        """Emit one closed receipt result without an extension bag."""
        if outcome not in {
            "preflight-rejected",
            "storage-rejected",
            "created",
            "committed-existing",
            "reused",
            "collision",
            "invalid-existing-receipt",
            "write-failed",
            "commit-failed",
            "interrupted",
        }:
            raise ValueError(f"invalid roadmap escalation outcome: {outcome!r}")
        if handoff not in {None, "requires-scope-review"}:
            raise ValueError(f"invalid roadmap escalation handoff: {handoff!r}")
        if outcome in {"created", "committed-existing", "reused"}:
            if (
                not isinstance(receipt_id, str)
                or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(receipt_id) is None
                or handoff != "requires-scope-review"
            ):
                raise ValueError(
                    "durable roadmap escalation results require receipt identity and handoff"
                )
        elif receipt_id is not None or handoff is not None:
            raise ValueError("non-durable roadmap escalation results must not expose receipt facts")
        ev = RoadmapEscalationResult(
            ts=utc_now_iso(),
            run_id=self.run_id,
            outcome=outcome,  # type: ignore[arg-type]
            receipt_id=receipt_id,
            handoff=handoff,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def roadmap_impact_preflight(
        self,
        *,
        receipt_final: Optional[str],
        artifact_key: Optional[str],
        feedback_id: Optional[str],
        reason: Optional[str],
        target_kind: Optional[str],
        target_id: Optional[str],
        receipt_source_digest: Optional[str],
        source_record_digest: Optional[str],
        brief_digest: Optional[str],
        snapshot_artifact_count: Optional[int],
        closure_node_count: Optional[int],
        closure_relation_count: Optional[int],
        closure_mapping_failures: Optional[tuple[tuple[int, int, int], ...]],
        verdict: str,
    ) -> None:
        """Emit one closed impact admission result without an extension bag."""
        if verdict not in {
            "mode-rejected",
            "final-rejected",
            "receipt-missing",
            "receipt-unreadable",
            "receipt-invalid",
            "receipt-rejected",
            "changed-brief",
            "legacy-brief",
            "snapshot-rejected",
            "closure-rejected",
            "accepted",
            "interrupted",
        }:
            raise ValueError(f"invalid roadmap impact preflight verdict: {verdict!r}")
        # Same hand-copied vocabulary as RoadmapEscalationPreflight.reason
        # above, preserving this leaf module's no-first-party-import boundary.
        if reason is not None and reason not in {
            "prose",
            "row-structure",
            "collection-structure",
            "relationship-semantics",
            "decision-semantics",
            "cross-artifact-impact",
        }:
            raise ValueError(f"invalid roadmap impact reason: {reason!r}")
        if target_kind is not None and target_kind not in {"artifact", "row"}:
            raise ValueError(f"invalid roadmap impact target kind: {target_kind!r}")
        _validate_roadmap_impact_preflight_facts(
            receipt_final=receipt_final,
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            reason=reason,
            target_kind=target_kind,
            target_id=target_id,
            receipt_source_digest=receipt_source_digest,
            source_record_digest=source_record_digest,
            brief_digest=brief_digest,
            snapshot_artifact_count=snapshot_artifact_count,
            closure_node_count=closure_node_count,
            closure_relation_count=closure_relation_count,
            closure_mapping_failures=closure_mapping_failures,
            verdict=verdict,
        )
        ev = RoadmapImpactPreflight(
            ts=utc_now_iso(),
            run_id=self.run_id,
            receipt_final=receipt_final,
            artifact_key=artifact_key,
            feedback_id=feedback_id,
            reason=reason,  # type: ignore[arg-type]
            target_kind=target_kind,  # type: ignore[arg-type]
            target_id=target_id,
            receipt_source_digest=receipt_source_digest,
            source_record_digest=source_record_digest,
            brief_digest=brief_digest,
            snapshot_artifact_count=snapshot_artifact_count,
            closure_node_count=closure_node_count,
            closure_relation_count=closure_relation_count,
            closure_mapping_failures=closure_mapping_failures,
            verdict=verdict,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def roadmap_impact_result(
        self,
        *,
        outcome: str,
        analysis_id: Optional[str],
        route_class: Optional[str],
        publication_outcome: Optional[str],
        next_workflow: Optional[str],
    ) -> None:
        """Emit one closed impact terminal result without an extension bag."""
        if outcome not in {
            "completed",
            "preflight-rejected",
            "changed-brief",
            "legacy-brief",
            "invalid",
            "storage-rejected",
            "collision",
            "write-failed",
            "interrupted",
        }:
            raise ValueError(f"invalid roadmap impact outcome: {outcome!r}")
        if outcome != "completed":
            if any(
                value is not None
                for value in (
                    analysis_id,
                    route_class,
                    publication_outcome,
                    next_workflow,
                )
            ):
                raise ValueError(
                    "non-completed roadmap impact results must not expose analysis facts"
                )
        else:
            if (
                not isinstance(analysis_id, str)
                or _ROADMAP_ESCALATION_SHA256_RE.fullmatch(analysis_id) is None
                or route_class not in {"same-artifact", "cross-artifact", "requires-scope-review"}
                or publication_outcome not in {"created", "reused"}
            ):
                raise ValueError(
                    "completed roadmap impact results require identity, route, and publication"
                )
            expected_workflow = {
                "same-artifact": "roadmap-same-artifact-structural-revision",
                "cross-artifact": "roadmap-cross-artifact-revision-transaction",
                "requires-scope-review": None,
            }[route_class]
            if next_workflow != expected_workflow:
                raise ValueError("roadmap impact workflow must match its completed route class")
        ev = RoadmapImpactResult(
            ts=utc_now_iso(),
            run_id=self.run_id,
            outcome=outcome,  # type: ignore[arg-type]
            analysis_id=analysis_id,
            route_class=route_class,  # type: ignore[arg-type]
            publication_outcome=publication_outcome,  # type: ignore[arg-type]
            next_workflow=next_workflow,  # type: ignore[arg-type]
        )
        self._emit(ev)

    def claude_stream_event(
        self,
        *,
        phase: str,
        attempt: int,
        kind: str,
        tool_name: Optional[str] = None,
        tool_input_summary: Optional[str] = None,
        bytes_in_delta: int = 0,
        **extra: Any,
    ) -> None:
        """Emit one :class:`ClaudeStreamEvent`.

        Step 2 of the Claude Call Observability plan calls this from
        the stdout pump in ``_run_streaming_once`` once per NDJSON line
        parsed out of ``claude -p --output-format stream-json``. The
        per-line elision in :func:`_append_jsonl_line` keeps the
        ``tool_input_summary`` field under the ``_MAX_LINE_BYTES`` cap
        even if a caller forgets to truncate to 200 chars themselves.
        """
        ev = ClaudeStreamEvent(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            kind=kind,
            tool_name=tool_name,
            tool_input_summary=tool_input_summary,
            bytes_in_delta=bytes_in_delta,
        )
        self._emit(ev, **extra)

    def claude_call_progress(
        self,
        *,
        phase: str,
        attempt: int,
        elapsed_ms: int,
        silent_ms: int,
        last_tool: Optional[str] = None,
        last_activity_kind: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Emit one :class:`ClaudeCallProgress` heartbeat.

        Step 2's progress daemon thread calls this every
        ``PROGRESS_INTERVAL_S`` while a ``claude -p`` subprocess is in
        flight. Persisting the heartbeat to JSONL (rather than only to
        the terminal) is what lets post-hoc tooling reason about a
        stalled call after the operator has closed the window.
        """
        ev = ClaudeCallProgress(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            elapsed_ms=elapsed_ms,
            silent_ms=silent_ms,
            last_tool=last_tool,
            last_activity_kind=last_activity_kind,
        )
        self._emit(ev, **extra)
        # Deliberately no ``status`` kwarg — a late heartbeat must never
        # overwrite a newer ``backend_termination``/``backend_recovery_wait``
        # status; see ``_refresh_in_flight``.
        self._refresh_in_flight(
            elapsed_ms=elapsed_ms,
            silent_ms=silent_ms,
            last_tool=last_tool,
            last_activity_kind=last_activity_kind,
        )

    def claude_call_stall_suspected(
        self,
        *,
        phase: str,
        attempt: int,
        silent_ms: int,
        threshold_ms: int,
        last_tool: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Emit one :class:`ClaudeCallStallSuspected` marker.

        Fired once per ``(phase, attempt)`` when ``silent_ms`` crosses
        ``STALL_THRESHOLD_S``. The progress daemon owns the
        "fire once" debouncing — this method itself is happy to be
        called multiple times; the JSONL is append-only and downstream
        tooling already tolerates duplicate stall markers (it picks
        the earliest by ``ts``).
        """
        ev = ClaudeCallStallSuspected(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            silent_ms=silent_ms,
            threshold_ms=threshold_ms,
            last_tool=last_tool,
        )
        self._emit(ev, **extra)

    @contextmanager
    def bind_shell_sink(self, *, phase: str, attempt: int) -> Iterator[None]:
        """Install a shell sink that forwards ``ClaudeCallEnd`` events
        to this writer for the duration of the ``with`` block.

        Step 2's ``plan_tool.shell.claude_invoke`` emits one
        ``ClaudeCallEnd`` per call when a sink is installed. The sink
        rewrites the event's empty ``run_id`` and overrides
        ``phase`` / ``attempt`` with the bind-time values before
        appending the merged payload to our JSONL.

        The override is load-bearing for callers like
        ``launcher.run_step`` and ``launcher.apply_finding``: they
        call the wrapper ``shell_invoker(prompt)``, which delegates
        to ``claude_invoke(prompt)`` *without* threading
        ``phase`` / ``attempt`` through, so the shell-side event
        arrives with the default ``"claude_invoke"`` / ``1`` labels.
        Substituting the caller's labels here is what makes
        ``runs diff`` able to tell a ``claude_call`` event apart
        from an ``apply_finding_dispatch`` event.

        On exit (success or exception) the previous sink is
        restored, so a missing-``claude``-binary raise during
        ``invoker(prompt)`` doesn't leak a stale sink onto the next
        call.
        """
        # Local import keeps run_log.py free of a first-party import
        # cycle at module load time. ``shell`` is a leaf module that
        # imports from ``run_log``, not vice-versa.
        from plan_tool import shell

        prev_sink = shell.get_active_sink()
        prev_writer = shell.get_active_run_logger()
        _sink = _make_call_end_sink(
            run_id=self.run_id,
            log_path=self.log_path,
            phase=phase,
            attempt=attempt,
            context_getter=self._current_context,
            on_event=self._record_usage,
        )

        shell.set_active_sink(_sink)
        shell.set_active_run_logger(self)
        try:
            yield
        finally:
            shell.set_active_sink(prev_sink)
            shell.set_active_run_logger(prev_writer)

    @contextmanager
    def telemetry_run_id_scope(self) -> Iterator[None]:
        """Bind the telemetry active ``run_id`` to this writer's ``run_id``
        for the block, restoring the prior value on every exit path.

        Opt-in: only the two ``run`` entrypoints (``cmd_run`` /
        ``_cmd_run_sweep``) call it, so a ``record_decision`` fired mid-run
        carries the run's ``run_id`` while the other ~13 ``start`` sites leave
        the ContextVar at its ``""`` default (phase-2 backfill). Delegates to
        step-1's :func:`telemetry.scoped_run_id` so the token reset lives in
        one place. Imports ``telemetry`` lazily — same as the sink helpers'
        ``shell`` import — to keep this module's no-first-party-import leaf
        boundary; ``telemetry`` is itself a stdlib-only leaf, so no cycle.
        """
        from plan_tool import telemetry

        with telemetry.scoped_run_id(self.run_id):
            yield

    def install_call_end_sink(self, phase: str, attempt: int) -> None:
        """Stateful counterpart to :meth:`bind_shell_sink` with
        ``phase``/``attempt`` *override*.

        Used by callers like ``create.py`` where the invoker wrapper
        (``shell_claude_invoker(prompt)``) doesn't propagate
        ``phase``/``attempt`` kwargs through to ``shell.claude_invoke`` —
        the shell-side event arrives with the defaults (``"claude_invoke"``
        / ``1``) and we want the run log to record the *caller*'s
        phase label instead.

        Pair with :meth:`uninstall_call_end_sink`. Prefer
        :meth:`bind_shell_sink` where a scoped block fits: the two write
        identical payloads (both share :func:`_make_call_end_sink`) and
        differ only in lifecycle — that variant restores the previous sink
        on exit, including on an exception, and nests.
        """
        from plan_tool import shell

        _sink = _make_call_end_sink(
            run_id=self.run_id,
            log_path=self.log_path,
            phase=phase,
            attempt=attempt,
            context_getter=self._current_context,
            on_event=self._record_usage,
        )

        self._prev_shell_sinks.append(shell.get_active_sink())
        self._prev_run_loggers.append(shell.get_active_run_logger())
        shell.set_active_sink(_sink)
        shell.set_active_run_logger(self)

    def uninstall_call_end_sink(self) -> None:
        """Restore the sink that was active before the matching
        :meth:`install_call_end_sink`. Pops the prev-sink stack so
        nested install/uninstall pairs unwind correctly. Safe to call
        without a matching install (no-op when the stack is empty)."""
        from plan_tool import shell

        if not self._prev_shell_sinks:
            return
        prev = self._prev_shell_sinks.pop()
        prev_writer = self._prev_run_loggers.pop()
        shell.set_active_sink(prev)
        shell.set_active_run_logger(prev_writer)

    def parse_failure(
        self,
        *,
        phase: str,
        attempt: int,
        failure_path: str,
        **extra: Any,
    ) -> None:
        """Emit a ``parse_failure`` event referencing the on-disk dump.

        ``failure_path`` is the relative path under
        ``.plan-tool/parse-failures/<slug>/<NN>-attemptK-<ts>.txt``
        that ``detail._log_parse_failure`` already wrote — the event
        is a pointer, not a duplicate payload, so the JSONL line
        stays under the 4096-byte cap regardless of how big the raw
        response was.
        """
        ev = ParseFailure(
            ts=utc_now_iso(),
            run_id=self.run_id,
            phase=phase,
            attempt=attempt,
            failure_path=failure_path,
        )
        self._emit(ev, **extra)

    # ---- checkpoint helpers (parity with planned consumers) ----

    def audit_pass_end(
        self,
        *,
        pass_number: int,
        cap: int,
        outcome: str,
        new_ids: list[str],
        material_new_ids: list[str],
        unique_so_far: int,
        **extra: Any,
    ) -> None:
        """Emit ``audit_pass_end`` — the per-pass yield the saved report omits."""
        ev = AuditPassEnd(
            ts=utc_now_iso(),
            run_id=self.run_id,
            pass_number=pass_number,
            cap=cap,
            outcome=outcome,
            new_count=len(new_ids),
            material_new_count=len(material_new_ids),
            new_ids=new_ids[:_AUDIT_PASS_IDS_CAP],
            material_new_ids=material_new_ids[:_AUDIT_PASS_IDS_CAP],
            unique_so_far=unique_so_far,
        )
        self._emit(ev, **extra)

    def checkpoint_hit(
        self,
        name: str,
        input_hash: str,
        payload_bytes: int,
        **extra: Any,
    ) -> None:
        ev = CheckpointHit(
            ts=utc_now_iso(),
            run_id=self.run_id,
            name=name,
            input_hash=input_hash,
            payload_bytes=payload_bytes,
        )
        self._emit(ev, **extra)

    def checkpoint_save(
        self,
        name: str,
        input_hash: str,
        payload_bytes: int,
        **extra: Any,
    ) -> None:
        ev = CheckpointSave(
            ts=utc_now_iso(),
            run_id=self.run_id,
            name=name,
            input_hash=input_hash,
            payload_bytes=payload_bytes,
        )
        self._emit(ev, **extra)

    def checkpoint_discard(
        self,
        name: str,
        reason: str,
        **extra: Any,
    ) -> None:
        ev = CheckpointDiscard(
            ts=utc_now_iso(),
            run_id=self.run_id,
            name=name,
            reason=reason,
        )
        self._emit(ev, **extra)

    # ---- run termination ----

    def _emit_terminal(self, ev: Event, extra: dict[str, Any]) -> None:
        """Write ``run_end``, dropping an oversize ``result`` rather than raising.

        ``run_end`` is emitted from ``finally`` blocks, so a
        :class:`RunLogLineTooLarge` there would replace the command's own return
        code or exception. The other fields fit on their own (``error`` is
        elided at ``_MAX_STRING_LEN_IN_PAYLOAD`` characters), so only the
        command's ``result`` can push the line over; it is dropped and flagged
        ``result_dropped``.
        """
        try:
            self._emit(ev, **extra)
        except RunLogLineTooLarge:
            if "result" not in extra:
                raise
            without_result = {k: v for k, v in extra.items() if k != "result"}
            self._emit(ev, **without_result, result_dropped=True)

    def _record_usage(self, event: ClaudeCallEnd) -> None:
        with self._usage_lock:
            self._usage["calls"] += 1
            for name in _USAGE_FIELDS:
                value = getattr(event, name)
                if value is not None:
                    self._usage[name][0] += value
                    self._usage[name][1] += 1

    def _usage_totals(self) -> Optional[dict[str, Any]]:
        """``run_end.usage``: each field is the sum over the calls that reported
        it, ``None`` when no call did. A field only some calls reported is named
        in ``partial_fields``, so its sum reads as a lower bound, never complete.
        ``None`` overall when the run made no backend call."""
        with self._usage_lock:
            calls = self._usage["calls"]
            if calls == 0:
                return None
            totals: dict[str, Any] = {"calls": calls}
            partial: list[str] = []
            for name in _USAGE_FIELDS:
                total, reported = self._usage[name]
                if reported == 0:
                    totals[name] = None
                    continue
                totals[name] = round(total, 6) if name == "cost_usd" else total
                if reported < calls:
                    partial.append(name)
            totals["partial_fields"] = partial
            totals["cost_usd_basis"] = "api-equivalent estimate, not a charge"
            return totals

    def run_end(
        self,
        *,
        outcome: str,
        rc: int,
        error: Optional[str] = None,
        termination_reason: Optional[str] = None,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit the terminating ``run_end`` event and remove the
        in-flight snapshot.

        Safe to call from a single ``finally:`` covering every return
        path. Cleanup of the snapshot file is best-effort: a missing
        file is fine, and other ``OSError`` cases are swallowed so a
        broken filesystem can't escalate a successful run into a
        failure on the way out.

        The unlink is also *guarded*: before removing the file, this
        reads it back and skips the delete when its ``run_id`` names a
        different run. That happens when a newer same-slug
        ``RunLogWriter.start()`` has since overwritten the snapshot — a
        completing call's teardown must not erase a still-running
        sibling's only liveness signal out from under it. An unreadable
        or missing snapshot proceeds with the unlink exactly as before
        this guard existed.

        ``termination_reason`` defaults to the most recent reason
        recorded by :meth:`backend_termination` / :meth:`run_interrupted`
        on this writer, so the 23 existing call sites that never pass it
        keep working unchanged. Pass it explicitly to override the
        tracked value. Omitted from the payload entirely (not emitted as
        ``None``) when neither an explicit value nor a tracked one
        resolves — a run with no backend-lane activity (``jira``,
        ``annotate``, ...) keeps today's exact ``run_end`` shape.

        ``result`` is the command's artifact record (``create`` / ``detail``),
        see DATA_CONTRACT.md; it is omitted from the payload when not passed.
        """
        duration_ms = int((time.monotonic() - self._started_monotonic) * 1000)
        ev = RunEnd(
            ts=utc_now_iso(),
            run_id=self.run_id,
            duration_ms=duration_ms,
            outcome=outcome,
            rc=rc,
        )
        resolved_termination_reason = (
            termination_reason if termination_reason is not None else self._last_termination_reason
        )
        payload_extra: dict[str, Any] = {}
        if error:
            payload_extra["error"] = error
        if resolved_termination_reason:
            payload_extra["termination_reason"] = resolved_termination_reason
        if result is not None:
            payload_extra["result"] = result
        usage = self._usage_totals()
        if usage is not None:
            payload_extra["usage"] = usage
        self._emit_terminal(ev, payload_extra)
        try:
            with _in_flight_snapshot_guard(self.in_flight_path):
                on_disk = read_in_flight(self.in_flight_path)
                if on_disk is not None and on_disk.get("run_id") != self.run_id:
                    # A newer same-slug run has since claimed the snapshot;
                    # leave its liveness signal in place.
                    return
                try:
                    self.in_flight_path.unlink()
                except FileNotFoundError:
                    pass
        except OSError:
            # Best-effort cleanup; the next run will overwrite anyway.
            pass
