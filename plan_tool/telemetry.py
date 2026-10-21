"""Decision telemetry: an append-only record of heuristic and explicit
operator decisions plus their context.

This is phase 1 — passive **decision** capture. Outcome-linkage (tying a
decision to what later happened) and the read-only ``plan-tool telemetry``
analysis-and-recommend surface are deferred; this module just records the
events a later aggregation reads.

Design:

- **stdlib-only leaf** — imports nothing first-party, so any module (including
  cycle-sensitive leaves like ``granularity``) can record without a cycle.
- **best-effort** — ``record_decision`` swallows every error and never raises
  into the caller. An explicit recorder may acknowledge its ``False`` result;
  observational producers ignore it.
- **append-only JSONL** at ``<repo>/.plan-tool/telemetry/decisions.jsonl`` (one
  event per line, completed under an advisory append lock), mirroring
  ``run_log``. Gitignored and local.

The event schema is documented in ``DATA_CONTRACT.md`` (drift-guarded).
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

try:  # POSIX advisory locking.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised on Windows.
    _fcntl = None

try:  # Windows advisory byte-range locking.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX.
    _msvcrt = None

# Bump only on a breaking event-shape change; the reader tolerates older lines.
TELEMETRY_SCHEMA_VERSION = 3

_REL = (".plan-tool", "telemetry", "decisions.jsonl")
# A single event is small + structured; cap defensively so a pathological
# context bag can't write a multi-megabyte line.
_MAX_LINE_BYTES = 64 * 1024


@dataclass
class DecisionEvent:
    """One heuristic or explicitly recorded operator decision.

    ``kind`` is the decision family (e.g. ``"granularity"`` / ``"audit-coverage"``
    / ``"decomposition-decision"``); ``decision`` is the specific call within it;
    ``context`` is an open per-``kind`` bag of inputs or explicit rationale.

    The five defaulted join keys (``decision_id`` / ``run_id`` /
    ``plan_fingerprint`` / ``code_fingerprint`` / ``anchor``) let a later outcome
    resolver tie a decision to what happened after it. ``decision_id`` is a stable
    handle to a *class* of content-identical decisions, not a per-row key — see
    ``DATA_CONTRACT.md``.
    """

    schema_version: int
    ts: str
    kind: str
    decision: str
    plan_slug: str
    context: dict[str, Any] = field(default_factory=dict)
    decision_id: str = ""
    run_id: str = ""
    plan_fingerprint: str = ""
    code_fingerprint: str = ""
    anchor: str = ""


def telemetry_path(repo_root: Path) -> Path:
    return repo_root.joinpath(*_REL)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# The active run's id, read by ``record_decision`` at call time. Thread-scoped
# (a ``ContextVar``, mirroring ``shell._active_sink``) and set once at the run
# boundary by the run entrypoints; ``""`` when no run is active.
_active_run_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "plan_tool_active_run_id", default=""
)


def set_active_run_id(run_id: str) -> contextvars.Token:
    """Bind the active run id; returns the reset ``Token`` (mirrors
    ``shell.set_active_sink``'s token-based pair). Prefer :func:`scoped_run_id`."""
    return _active_run_id.set(str(run_id))


@contextlib.contextmanager
def scoped_run_id(run_id: str) -> Iterator[None]:
    """Bind ``run_id`` for the duration of the block, resetting on exit so
    nested/sequential runs restore correctly."""
    token = set_active_run_id(run_id)
    try:
        yield
    finally:
        _active_run_id.reset(token)


def _compute_decision_id(
    *,
    schema_version: int,
    kind: str,
    decision: str,
    plan_slug: str,
    plan_fingerprint: str,
    step_id: Optional[str],
    ts: str,
) -> str:
    """Stable stdlib hash of a decision's identity fields, truncated to 16 hex.

    ``run_id`` / ``code_fingerprint`` / ``anchor`` / ``context`` are deliberately
    out: they are join keys, not identity. A stable handle to a *class* of
    content-identical rows, not a per-row key — see ``DATA_CONTRACT.md``.
    """
    payload = json.dumps(
        [
            schema_version,
            kind,
            decision,
            plan_slug,
            plan_fingerprint,
            "" if step_id is None else str(step_id),
            ts,
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


_CODE_FINGERPRINT_DIGEST_FORMAT = "plan-tool-code-fingerprint-v1"


def code_fingerprint_digest(code_fingerprint: Mapping[str, str]) -> str:
    """Return the canonical SHA-256 identity for a computed code fingerprint.

    The tagged compact-JSON frame contains path/hash pairs sorted by path.  Both
    values are opaque strings; no code files are consulted.  An explicitly
    computed empty mapping therefore has a real, non-empty identity.
    """
    frame = json.dumps(
        [
            _CODE_FINGERPRINT_DIGEST_FORMAT,
            sorted(
                (
                    [str(path), str(content_hash)]
                    for path, content_hash in code_fingerprint.items()
                ),
                key=lambda pair: pair[0],
            ),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(frame.encode("utf-8")).hexdigest()


def _normalize_code_fingerprint(
    code_fingerprint: Optional[str | Mapping[str, str]],
) -> str:
    if code_fingerprint is None:
        return ""
    if isinstance(code_fingerprint, str):
        return code_fingerprint
    return code_fingerprint_digest(code_fingerprint)


def _acquire_append_lock(fd: int) -> Optional[str]:
    """Acquire a cross-process advisory lock, returning its implementation."""
    if _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        return "fcntl"
    if _msvcrt is not None:
        # ``msvcrt.locking`` locks bytes from the current file position. The
        # dedicated lock file may be new, so size it without routing through
        # ``os.write`` (whose short-write behavior is tested independently).
        if os.fstat(fd).st_size < 1:
            os.ftruncate(fd, 1)
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
        return "msvcrt"
    return None


def _release_append_lock(fd: int, implementation: str) -> None:
    if implementation == "fcntl" and _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
    elif implementation == "msvcrt" and _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)


def _append_json_line(path: Path, line: bytes) -> bool:
    """Append all of ``line`` transactionally, rolling back detected failures."""
    lock_fd: Optional[int] = None
    fd: Optional[int] = None
    lock_implementation: Optional[str] = None
    original_length = 0
    wrote = 0
    try:
        lock_fd = os.open(
            Path(f"{path}.lock"), os.O_RDWR | os.O_CREAT, 0o644
        )
        lock_implementation = _acquire_append_lock(lock_fd)
        if lock_implementation is None:
            return False
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        original_length = os.fstat(fd).st_size
        while wrote < len(line):
            progress = os.write(fd, line[wrote:])
            if progress <= 0:
                raise OSError("telemetry append made no progress")
            wrote += progress
        return True
    except Exception:
        if fd is not None and lock_implementation is not None and wrote:
            try:
                os.ftruncate(fd, original_length)
            except Exception:
                pass
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if lock_fd is not None:
            if lock_implementation is not None:
                try:
                    _release_append_lock(lock_fd, lock_implementation)
                except Exception:
                    pass
            try:
                os.close(lock_fd)
            except Exception:
                pass


def record_decision(
    repo_root: Path,
    *,
    kind: str,
    decision: str,
    plan_slug: str,
    context: Optional[dict[str, Any]] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
    anchor: str = "",
    step_id: Optional[str] = None,
    clock: Callable[[], str] = _utc_now_iso,
) -> bool:
    """Append one :class:`DecisionEvent`; return whether the full row persisted.

    Best-effort — never raises. Callers that do not need acknowledgement may
    ignore the return value.

    ``clock`` is injectable so tests can pin the timestamp. A pathologically
    large line (context bag over the cap) is dropped rather than raised.

    ``decision_id`` is minted here (the single writer of the log); ``run_id`` is
    read from the telemetry-owned ContextVar at call time. ``plan_fingerprint`` /
    ``code_fingerprint`` is normalized to a compact code-state digest;
    ``plan_fingerprint`` / ``anchor`` are caller-supplied join keys stored on the
    base event. ``step_id`` folds into the ``decision_id`` hash only (not stored).
    """
    try:
        ts = clock()
        event = DecisionEvent(
            schema_version=TELEMETRY_SCHEMA_VERSION,
            ts=ts,
            kind=str(kind),
            decision=str(decision),
            plan_slug=str(plan_slug),
            context=dict(context or {}),
            decision_id=_compute_decision_id(
                schema_version=TELEMETRY_SCHEMA_VERSION,
                kind=str(kind),
                decision=str(decision),
                plan_slug=str(plan_slug),
                plan_fingerprint=str(plan_fingerprint),
                step_id=step_id,
                ts=ts,
            ),
            run_id=_active_run_id.get(),
            plan_fingerprint=str(plan_fingerprint),
            code_fingerprint=_normalize_code_fingerprint(code_fingerprint),
            anchor=str(anchor),
        )
        line = (
            json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
            .encode("utf-8")
            + b"\n"
        )
        if len(line) > _MAX_LINE_BYTES:
            return False
        path = telemetry_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        return _append_json_line(path, line)
    except Exception:
        # Telemetry is observational; a failure here must not surface to the
        # caller or change the command's outcome.
        return False


# --- per-kind convenience recorders ---------------------------------------
# Each enforces a consistent ``context`` shape for one decision family so the
# later aggregation can rely on the keys. They take primitives (ints/strings),
# keeping this module a stdlib-only leaf — callers compute the counts from their
# own plan/finding types.

DECOMPOSITION_DECISION_KIND = "decomposition-decision"
DECOMPOSITION_DECISION_RECORDED = "recorded"
DECOMPOSITION_OUTCOMES = (
    "single",
    "split",
    "scope-out",
    "reframe",
    "withdraw",
    "defer",
)
_DECOMPOSITION_STEP_ANCHOR_RE = re.compile(r"step:(0|[1-9][0-9]*)\Z")


def decomposition_anchor_step_id(anchor: str) -> Optional[str]:
    """Return a canonical step id for ``step:<id>``, else ``None``."""
    match = _DECOMPOSITION_STEP_ANCHOR_RE.fullmatch(anchor)
    return match.group(1) if match else None


def record_decomposition_decision(
    repo_root: Path,
    *,
    plan_slug: str,
    outcome: str,
    anchor: str,
    rationale: str,
    plan_fingerprint: str = "",
) -> bool:
    """Record one explicit operator/session decomposition decision.

    This wrapper rejects an invalid public vocabulary before reaching the
    append-only primitive. Unlike observational callers, ``plan-tool decide``
    checks the returned acknowledgement and reports a failed persistence.
    """
    normalized_outcome = str(outcome)
    normalized_anchor = str(anchor)
    normalized_rationale = str(rationale).strip()
    step_id = decomposition_anchor_step_id(normalized_anchor)
    if (
        normalized_outcome not in DECOMPOSITION_OUTCOMES
        or not normalized_rationale
        or (normalized_anchor != "plan" and step_id is None)
    ):
        return False
    return record_decision(
        repo_root,
        kind=DECOMPOSITION_DECISION_KIND,
        decision=DECOMPOSITION_DECISION_RECORDED,
        plan_slug=plan_slug,
        context={"outcome": normalized_outcome, "rationale": normalized_rationale},
        plan_fingerprint=plan_fingerprint,
        anchor=normalized_anchor,
        step_id=step_id,
    )

CREATE_DECISION_REVIEW = "create-review"
CREATE_DECISION_STEP_OUTCOME = "create-step-outcome"

CREATE_ACTION_ACCEPT = "accept"
CREATE_ACTION_OVERRIDE = "override"
CREATE_ACTION_SPLIT_REQUESTED = "split-requested"
CREATE_ACTION_SPLIT_APPLIED = "split-applied"
CREATE_ACTION_SPLIT_UNUSABLE = "split-unusable"
CREATE_ACTION_SPLIT_INVALID = "split-invalid"
CREATE_ACTION_SPLIT_ERROR = "split-error"
CREATE_ACTION_UNCLASSIFIED_ACCEPTED = "unclassified-accepted"
CREATE_ACTION_UNCLASSIFIED_CLASSIFIED = "unclassified-classified"

CREATE_MODE_INTERACTIVE = "interactive"
CREATE_MODE_YES = "yes"
CREATE_MODE_NON_TTY = "non_tty"
CREATE_MODE_CHECKPOINT = "checkpoint"

# A per-plan split-criteria evaluation: its own decision family (not a new
# `granularity` decision). The `kind` literal is the contract downstream steps
# (the evaluator + drift-guard test) key on.
PLAN_CRITERIA_BREAKDOWN_KIND = "plan-criteria-breakdown"
PLAN_CRITERIA_DECISION = "evaluated"

# A pre-send prompt-budget check verdict: its own decision family. The `kind`
# literal is the contract the drift-guard test and later aggregation key on.
PROMPT_BUDGET_KIND = "prompt-budget"
BACKEND_PATTERN_MISS_KIND = "backend-pattern-miss"
BACKEND_PATTERN_MISS_DECISION = "plan-quota-candidate"
PROMPT_BUDGET_DECISION = "estimated"

# The reconcile drift-gate (`refresh.py:refresh_plan`) verdict: its own decision
# family. The `kind`/`decision` literals are the contract downstream aggregation
# keys on; the three verdict literals are the recorded `context.verdict` values.
DRIFT_GATE_KIND = "drift-gate"
DRIFT_GATE_DECISION = "gated"
DRIFT_VERDICT_NO_BASELINE = "no-baseline"
DRIFT_VERDICT_NO_DRIFT = "no-drift"
DRIFT_VERDICT_DRIFTED = "drifted"

# The per-finding apply-verdict producer (`launcher.py:apply_finding`): its own
# decision family. The recorded `context.verdict` is the parsed apply token
# (APPLIED / NOT-APPLICABLE / BLOCKED /
# BLOCKED-STRUCTURAL, UNKNOWN when the apply ran but emitted no token, or
# INVOCATION-FAILED when the backend did not return a usable response).
APPLY_VERDICT_KIND = "apply-verdict"
APPLY_VERDICT_DECISION = "recorded"
APPLY_VERDICT_INVOCATION_FAILED = "INVOCATION-FAILED"

# The escalate-to-split bridge (`launcher.py:escalate_to_split`) disposition: its
# own decision family. The single `decision` literal is `resolved`; the varying
# `EscalateResult.outcome` lives in `context` (like convergence's `verdict`). The
# `kind`/`decision` literals are the contract downstream aggregation keys on.
ESCALATE_SPLIT_KIND = "escalate-split"
ESCALATE_SPLIT_DECISION = "resolved"

# A structural-split mutation's new step titles: its own decision family,
# read back by #238's plan-mass "audit-induced growth" ratio to tell a step
# the plan author wrote from one a structural remedy inserted. Recorded at
# both tool-mediated creation paths (`detail.split_step` — `plan-tool split` —
# and `launcher.escalate_to_split`'s `applied` outcome). Keyed on title, not
# step id: a split renumbers every
# downstream step (`create._apply_step_split`'s contiguous-1..N invariant),
# so an id recorded at one split can point at a different step after a
# later one — titles survive renumbering and `split_step` already requires
# them unique within one split. A step added through a direct plan edit
# is not observable here and is never counted.
STEP_PROVENANCE_KIND = "step-provenance"
STEP_PROVENANCE_DECISION = "created"


def record_granularity(
    repo_root: Path,
    *,
    plan_slug: str,
    stage: str,
    steps: int,
    split: int,
    merge: int,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record a granularity assessment: how many split/merge signals fired on a
    plan of ``steps`` steps, at which ``stage`` (create/detail/completeness).

    ``plan_fingerprint``/``code_fingerprint`` are defaulted base-event join keys a
    caller with a plan can supply; most call sites pass nothing (phase-2 backfill)."""
    record_decision(
        repo_root,
        kind="granularity",
        decision="assessed",
        plan_slug=plan_slug,
        context={"stage": stage, "steps": steps, "split": split, "merge": merge},
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


# The reconcile-lane code-reveals-a-split detector's fire event. Its own
# decision literal (not "assessed") so #72 aggregation can isolate this
# low-confidence, built/un-built proxy signal and measure its fire — and, once
# outcome-linkage lands, acted-on / false-positive — rate from telemetry rather
# than a manual study (BACKLOG #117).
CODE_REVEALS_SPLIT_DECISION = "code-reveals-split"


def record_code_reveals_split(
    repo_root: Path,
    *,
    plan_slug: str,
    steps: int,
    step_ids: list[str],
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record one reconcile-lane fire of the code-reveals-a-split detector: which
    steps it flagged on a plan of ``steps`` steps. Keeps ``step_ids`` (stable
    across passes) so a later outcome pass can see whether the flagged step was
    actually split (BACKLOG #117 measurement, folded into #72).

    ``step_ids`` is plural with no single step focus, so no ``step_id`` folds into
    the ``decision_id`` hash. ``plan_fingerprint``/``code_fingerprint`` are the
    defaulted base-event join keys."""
    record_decision(
        repo_root,
        kind="granularity",
        decision=CODE_REVEALS_SPLIT_DECISION,
        plan_slug=plan_slug,
        context={
            "stage": "reconcile",
            "steps": steps,
            "fired": len(step_ids),
            "step_ids": list(step_ids),
        },
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_create_granularity_assessment(
    repo_root: Path,
    *,
    plan_slug: str,
    assessment_id: str,
    steps: int,
    candidate_fingerprint: str,
    file_footprint: int,
    split: int,
    split_steps: int,
    merge: int,
    split_step_ids: list[str],
    predicate_counts: dict[str, int],
    can_split: bool,
    mode: str,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> bool:
    """Record one create-stage granularity assessment pass.

    ``assessment_id`` identifies this observed pass and joins its outcomes.
    ``plan_fingerprint``/``code_fingerprint`` are the defaulted base-event join
    keys; the create-candidate ``candidate_fingerprint`` context key is distinct."""
    if not assessment_id:
        return False
    return record_decision(
        repo_root,
        kind="granularity",
        decision=CREATE_DECISION_REVIEW,
        plan_slug=plan_slug,
        context={
            "stage": "create",
            "assessment_id": assessment_id,
            "steps": steps,
            "candidate_fingerprint": candidate_fingerprint,
            "file_footprint": file_footprint,
            "split": split,
            "split_steps": split_steps,
            "merge": merge,
            "split_step_ids": list(split_step_ids),
            "predicate_counts": dict(predicate_counts),
            "can_split": bool(can_split),
            "mode": mode,
        },
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_create_step_outcome(
    repo_root: Path,
    *,
    plan_slug: str,
    assessment_id: str,
    step_id: str,
    had_split_hint: bool,
    action: str,
    proposed_change_type: Optional[str],
    resolved_change_type: Optional[str],
    before_steps: Optional[int] = None,
    after_steps: Optional[int] = None,
    error_class: Optional[str] = None,
    plan_fingerprint: str = "",
) -> None:
    """Record one create-stage operator answer.

    Split-only keys are omitted when absent; a missing key means "not
    applicable", not zero. ``step_id`` is dual-used: kept as a context key and
    also folded into the ``decision_id`` hash so step-scoped create decisions
    sharing a second-precision ``ts`` stop colliding.
    ``assessment_id`` joins the outcome to its successfully persisted review.
    Code state belongs only to that review, so this recorder leaves the base
    event's ``code_fingerprint`` at the empty sentinel.
    """
    if not assessment_id:
        return
    context: dict[str, Any] = {
        "assessment_id": assessment_id,
        "step_id": step_id,
        "had_split_hint": bool(had_split_hint),
        "action": action,
        "proposed_change_type": proposed_change_type,
        "resolved_change_type": resolved_change_type,
    }
    if before_steps is not None:
        context["before_steps"] = before_steps
    if after_steps is not None:
        context["after_steps"] = after_steps
    if error_class is not None:
        context["error_class"] = error_class
    record_decision(
        repo_root,
        kind="granularity",
        decision=CREATE_DECISION_STEP_OUTCOME,
        plan_slug=plan_slug,
        context=context,
        step_id=step_id,
        plan_fingerprint=plan_fingerprint,
    )


def record_audit_coverage(
    repo_root: Path,
    *,
    plan_slug: str,
    passes: int,
    budget_limited: bool,
    findings: int,
    steps: int,
    early_stop_reason: Optional[str] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record conceptual-audit coverage: passes, its unconfirmed-stop reason,
    and findings/size — the data that would tune the static pass count (#59/#60).

    ``plan_fingerprint``/``code_fingerprint`` are the defaulted base-event keys."""
    record_decision(
        repo_root,
        kind="audit-coverage",
        decision="passes",
        plan_slug=plan_slug,
        context={
            "passes": passes,
            "budget_limited": bool(budget_limited),
            "early_stop_reason": early_stop_reason,
            "findings": findings,
            "steps": steps,
        },
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_convergence(
    repo_root: Path,
    *,
    plan_slug: str,
    verdict: str,
    runs: int,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record a ``plan-tool convergence`` verdict (no-history /
    insufficient-history / converging) and how many saved runs it read.

    ``plan_fingerprint``/``code_fingerprint`` are the defaulted base-event keys."""
    record_decision(
        repo_root,
        kind="convergence",
        decision="diagnosed",
        plan_slug=plan_slug,
        context={"verdict": verdict, "runs": runs},
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_plan_criteria_breakdown(
    repo_root: Path,
    *,
    plan_slug: str,
    plan_fingerprint: str,
    criteria: list[dict[str, Any]],
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record one per-plan split-criteria evaluation.

    ``plan_fingerprint`` is a caller-computed digest (this stdlib-only leaf never
    computes it); ``code_fingerprint`` is a caller-supplied digest or map that is
    normalized to the compact code-state identity. ``criteria`` is a passthrough bag of
    per-criterion rows (``id``/``fired``/``severity``/``step_ids``); the counts are
    derived here so caller and recorder can't drift on key names.

    Phase 1 homing: ``plan_fingerprint`` is **dual-homed** — forwarded to the
    base-event field *and* kept in ``context`` so the in-repo drift consumer
    (``split_criteria.py``) that reads ``event.context["plan_fingerprint"]`` keeps
    working; it is a short digest, so the duplicate is cheap. ``code_fingerprint``
    is **base-homed only** (not copied into ``context``): nothing reads it from
    ``context``. On the base field it serializes as ``""`` when unavailable.
    Phase 2 collapses
    ``plan_fingerprint`` to a single home too. See ``DATA_CONTRACT.md``.
    """
    rows = [dict(c) for c in criteria]
    context: dict[str, Any] = {
        "plan_fingerprint": plan_fingerprint,
        "criteria": rows,
        "criteria_count": len(rows),
        "fired_count": sum(1 for c in rows if c.get("fired")),
    }
    record_decision(
        repo_root,
        kind=PLAN_CRITERIA_BREAKDOWN_KIND,
        decision=PLAN_CRITERIA_DECISION,
        plan_slug=plan_slug,
        context=context,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_prompt_budget(
    repo_root: Path,
    *,
    plan_slug: str,
    phase: str,
    total_bytes: int,
    advisory: str,
    estimated_tokens: Optional[int] = None,
    context_window: Optional[int] = None,
    headroom_ratio: Optional[float] = None,
    blocks: Optional[tuple[tuple[str, int], ...]] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record one pre-send prompt-budget check verdict.

    ``phase`` is the assembly point the check ran at (e.g. ``"detail"`` /
    ``"run-step"`` / ``"shell-backstop"``); ``advisory`` is the caller-supplied
    ``PromptBudget.level`` string (``"ok"`` / ``"warn"`` / ``"high"``) — this
    stdlib-only leaf never imports ``prompt_budget``. The tuning primitives
    (``estimated_tokens`` / ``context_window`` / ``headroom_ratio``) and the
    per-block ``blocks`` breakdown are optional; each key is omitted when its
    argument is ``None`` (missing key means not-applicable, not zero).
    ``plan_slug`` may be ``""`` (the shell backstop often has no resolved plan).
    ``plan_fingerprint``/``code_fingerprint`` are the defaulted base-event keys.
    """
    context: dict[str, Any] = {
        "phase": phase,
        "total_bytes": total_bytes,
        "advisory": advisory,
    }
    if estimated_tokens is not None:
        context["estimated_tokens"] = estimated_tokens
    if context_window is not None:
        context["context_window"] = context_window
    if headroom_ratio is not None:
        context["headroom_ratio"] = headroom_ratio
    if blocks:
        context["blocks"] = [[str(n), int(b)] for n, b in blocks]
    record_decision(
        repo_root,
        kind=PROMPT_BUDGET_KIND,
        decision=PROMPT_BUDGET_DECISION,
        plan_slug=plan_slug,
        context=context,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_backend_pattern_miss(
    repo_root: Path,
    *,
    plan_slug: str,
    backend: str,
    classified_as: str,
    markers: tuple[str, ...],
    excerpt: str,
    phase: str,
) -> None:
    """Record redacted evidence for a provider-pattern near miss."""
    record_decision(
        repo_root,
        kind=BACKEND_PATTERN_MISS_KIND,
        decision=BACKEND_PATTERN_MISS_DECISION,
        plan_slug=plan_slug,
        context={
            "backend": backend,
            "classified_as": classified_as,
            "markers": list(markers),
            "excerpt": excerpt,
            "phase": phase,
        },
    )


def record_drift_gate(
    repo_root: Path,
    *,
    plan_slug: str,
    verdict: str,
    drifted_files: int,
    findings: int,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[str | Mapping[str, str]] = None,
) -> None:
    """Record one reconcile drift-gate (`refresh.py:refresh_plan`) verdict.

    ``verdict`` is one of ``DRIFT_VERDICT_NO_BASELINE`` / ``DRIFT_VERDICT_NO_DRIFT``
    / ``DRIFT_VERDICT_DRIFTED``; ``drifted_files``/``findings`` are the reconcile
    counts (both zero on the ``no-drift`` no-op). ``code_fingerprint`` is the
    already-computed code axis passed at every verdict; ``plan_fingerprint`` is
    caller-computed (this stdlib-only leaf never imports ``review_persistence``)
    and empty on the hot ``no-drift`` path. Both are defaulted base-event keys."""
    record_decision(
        repo_root,
        kind=DRIFT_GATE_KIND,
        decision=DRIFT_GATE_DECISION,
        plan_slug=plan_slug,
        context={
            "verdict": verdict,
            "drifted_files": drifted_files,
            "findings": findings,
        },
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
    )


def record_apply_verdict(
    repo_root: Path,
    *,
    plan_slug: str,
    verdict: str,
    step_id: Optional[str] = None,
    anchor: str = "",
    plan_fingerprint: str = "",
) -> None:
    """Record one per-finding apply verdict (`launcher.py:apply_finding`).

    ``verdict`` is the parsed apply token (``APPLIED`` / ``NOT-APPLICABLE`` /
    ``BLOCKED`` / ``BLOCKED-STRUCTURAL``, ``UNKNOWN`` when the apply ran but
    emitted no recognized token, or ``INVOCATION-FAILED`` when the backend
    returned non-zero or raised). ``step_id`` is the singular resolved step,
    folded into the ``decision_id`` hash (omitted from ``context`` when ``None``).
    ``anchor`` is the finding's join key on the base event — coerced to ``""``
    when falsy, since ``Recommendation.anchor`` is ``Optional[str]`` and an
    un-coerced ``None`` would serialize the literal ``"None"``. ``plan_fingerprint``
    is the caller-hoisted digest (no ``code_fingerprint`` — this per-finding site is
    plan_fingerprint-only)."""
    context: dict[str, Any] = {"verdict": verdict}
    if step_id is not None:
        context["step_id"] = step_id
    record_decision(
        repo_root,
        kind=APPLY_VERDICT_KIND,
        decision=APPLY_VERDICT_DECISION,
        plan_slug=plan_slug,
        context=context,
        step_id=step_id,
        anchor=str(anchor) if anchor else "",
        plan_fingerprint=plan_fingerprint,
    )


def record_escalate_split(
    repo_root: Path,
    *,
    plan_slug: str,
    outcome: str,
    allow_split: bool,
    step_id: Any,
    blocking: Optional[list[Any]] = None,
    plan_fingerprint: str = "",
) -> None:
    """Record one escalate-to-split bridge disposition (`launcher.py:escalate_to_split`).

    ``outcome`` is the frozen ``EscalateResult.outcome`` string — one of
    ``applied`` / ``recommended`` / ``unsafe`` / ``proposal-unusable`` /
    ``step-missing`` — kept in ``context`` (the varying value, like
    convergence's ``verdict``); ``decision`` is the fixed ``"resolved"``.
    ``allow_split`` records whether the caller permitted a mutation.

    ``step_id`` is dual-used: kept as a ``str`` context key and folded into the
    ``decision_id`` hash so step-scoped escalate decisions sharing a
    second-precision ``ts`` stop colliding. ``blocking`` (the ``unsafe`` ids,
    stored as strings) is omitted when empty — absence means "no blockers".

    ``plan_fingerprint`` only — escalate is a plan structure/safety decision, so
    it carries **no** ``code_fingerprint``. The caller computes the digest and
    passes it in (this stdlib-only leaf never imports a fingerprint producer)."""
    context: dict[str, Any] = {
        "outcome": outcome,
        "allow_split": bool(allow_split),
        "step_id": str(step_id),
    }
    if blocking:
        context["blocking"] = [str(b) for b in blocking]
    record_decision(
        repo_root,
        kind=ESCALATE_SPLIT_KIND,
        decision=ESCALATE_SPLIT_DECISION,
        plan_slug=plan_slug,
        context=context,
        step_id=str(step_id),
        plan_fingerprint=plan_fingerprint,
    )


def record_step_provenance(
    repo_root: Path,
    *,
    plan_slug: str,
    new_step_titles: list[str],
    mechanism: str,
    plan_fingerprint: str = "",
) -> None:
    """Record the titles of the step(s) one structural-split mutation just
    created.

    ``mechanism`` names the actuator: ``"split"`` for the shared
    ``detail.split_step`` primitive (``plan-tool split`` routes through
    it), or ``"escalate-split"`` for ``launcher.escalate_to_split``'s ``applied``
    outcome. ``new_step_titles`` are the freshly-inserted steps' titles only
    (never the surviving original's).

    Best-effort like every recorder here: a telemetry failure never
    surfaces to or changes the caller's mutation, which has already
    completed by the time this is called."""
    titles = [t for t in new_step_titles if t]
    if not titles:
        return
    record_decision(
        repo_root,
        kind=STEP_PROVENANCE_KIND,
        decision=STEP_PROVENANCE_DECISION,
        plan_slug=plan_slug,
        context={"new_step_titles": titles, "mechanism": mechanism},
        plan_fingerprint=plan_fingerprint,
    )


def read_step_provenance_titles(repo_root: Path, plan_slug: str) -> "set[str]":
    """Union of every step title ever recorded as structural-split-created
    for ``plan_slug``, across all recorded ``mechanism``s.

    Read-only aggregation over :func:`read_decisions`. Title-keyed rather
    than id-keyed — see :data:`STEP_PROVENANCE_KIND` — so it stays correct
    across later renumbers; it goes stale only if a step created by a split
    is subsequently retitled through a direct edit, which is the same
    unobservable direct-edit limit every provenance signal here has."""
    titles: set[str] = set()
    for event in read_decisions(repo_root):
        if event.kind != STEP_PROVENANCE_KIND or event.plan_slug != plan_slug:
            continue
        for raw_title in event.context.get("new_step_titles", []):
            if isinstance(raw_title, str) and raw_title:
                titles.add(raw_title)
    return titles


def read_decisions(repo_root: Path) -> list[DecisionEvent]:
    """Parse the decision log into events; skip blank/malformed lines.

    The reader the future aggregation/analysis surface builds on. Tolerant by
    design — a half-written or forward-version line is skipped, not fatal.
    """
    path = telemetry_path(repo_root)
    out: list[DecisionEvent] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
            out.append(
                DecisionEvent(
                    schema_version=int(d.get("schema_version", 0)),
                    ts=str(d.get("ts", "")),
                    kind=str(d.get("kind", "")),
                    decision=str(d.get("decision", "")),
                    plan_slug=str(d.get("plan_slug", "")),
                    context=dict(d.get("context", {})),
                    # New in schema 2; a v1 line lacks these — default each so it
                    # parses. Read the *stored* decision_id, never recompute it.
                    decision_id=str(d.get("decision_id", "")),
                    run_id=str(d.get("run_id", "")),
                    plan_fingerprint=str(d.get("plan_fingerprint", "")),
                    code_fingerprint=(
                        ""
                        if isinstance(d.get("code_fingerprint", ""), Mapping)
                        and not d.get("code_fingerprint")
                        else _normalize_code_fingerprint(
                            d.get("code_fingerprint", "")
                        )
                    ),
                    anchor=str(d.get("anchor", "")),
                )
            )
        except (ValueError, TypeError, AttributeError):
            continue
    return out
