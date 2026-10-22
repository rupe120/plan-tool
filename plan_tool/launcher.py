"""Orchestrate step execution: resolve step, render prompt, invoke claude, persist.

The `Invoker` type is the seam where real Claude invocation plugs in. Tests
substitute a fake invoker so the suite never spawns a subprocess.

The real `shell_invoker` shells out to `claude -p` mirroring what the legacy
`implement-plan.sh` does. This preserves the subprocess-per-step context
isolation that the redesign plan calls out as load-bearing.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Sequence, TextIO

from plan_tool.backend import (
    ClaudeRunStats,
    get_active_backend,
    get_active_spawn_cwd,
    provisional_backend_warning,
    registered_names,
    scoped_select_active_backend,
    spawn_cwd_from_repo_root,
    unknown_backend_override_warning,
)
from plan_tool import model_specs
# Re-exported for ``cli/app.py`` (console verbosity) and any caller that
# imported these names from ``launcher`` before the runner moved to its
# own leaf module. The threshold constants (``_PROGRESS_INTERVAL_S`` and
# friends) deliberately live only on ``backend_runner`` — patch them
# there, not here.
from plan_tool.backend_runner import (
    _CONSOLE_VERBOSITY_DEBUG,
    _CONSOLE_VERBOSITY_QUIET,
    _CONSOLE_VERBOSITY_VERBOSE,
    get_console_verbosity,
    run_streaming_once,
    set_console_verbosity,
)
from plan_tool.backend_config import BackendConfigError
from plan_tool.claude_errors import (
    ACTION_TO_RECOVERY,
    DEFAULT_RATE_LIMIT_FALLBACK_SECONDS,
    MAX_RATE_LIMIT_WAIT_SECONDS,
    RATE_LIMIT_PROMPT_LOCK,
    OnRateLimitAction,
    ask_on_rate_limit_action,
    build_streaming_classification_from_outcome,
    make_backend_recovery_sleep_seam,
    make_backend_recovery_wait_seam,
    make_plan_quota_pattern_miss_observer,
    resolve_on_rate_limit_policy,
)
from plan_tool.detail_artifacts import (
    DetailFormatError,
    require_supported_detail_format_version,
)
from plan_tool.parser import (
    UnsupportedPlanFormatVersionError,
    parse_plan,
    write_plan,
)
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter
from plan_tool.progress import ProgressReporter, StderrReporter
from plan_tool.locator import slug_from_filename
from plan_tool.model_response_sidecar import store_model_response_sidecar
from plan_tool.jira_grade import GRADE_RUN
from plan_tool.renderer import DetailGradeError, render_prompt
from plan_tool.response_contract import (
    APPLY_BASIC_VERDICT_RESPONSE_CONTRACT,
    APPLY_VERDICT_RESPONSE_CONTRACT,
    DEEP_VERDICT_RESPONSE_CONTRACT,
    FINDINGS_RESPONSE_CONTRACT,
)
from plan_tool.review_persistence import compute_plan_fingerprint
# Module-level (vs. lazy) so tests can monkeypatch these names on
# ``plan_tool.launcher``. ``prompt_budget`` is a near-leaf (only imports
# ``style``) and ``telemetry`` is a stdlib-only leaf, so neither creates an
# import cycle with ``launcher``.
from plan_tool.git_state import (
    changed_paths_or_none,
    committed_changed_paths,
    head_revision,
    make_partial_mutation_retry_guard,
)
from plan_tool.prompt_budget import (
    PromptBudget,
    estimate_prompt_budget,
    maybe_warn_prompt_budget,
    render_budget_summary,
)
from plan_tool.context_window import active_context_window
from plan_tool.rate_limit_loop import (
    RecoveryAction,
    run_with_rate_limit_recovery,
)
from plan_tool.telemetry import (
    APPLY_VERDICT_INVOCATION_FAILED,
    record_apply_verdict,
    record_escalate_split,
    record_prompt_budget,
    record_step_provenance,
)
from plan_tool.style import change_type_tag, warn
from plan_tool.review import (
    CARRIED_RESOLUTION_OPEN,
    RESTATED_PROPERTY_LABEL,
    CarriedFinding,
    FileCheck,
    FileExistence,
    Recommendation,
    confidence_label,
    format_recommendation_for_apply,
    restated_property_or_none,
    severity_label,
    StepFileCheck,
    _carried_severity_rank,
    _is_test_code_path,
    _make_rec_id,
    check_file_existence,
    detect_path_style_mismatch,
)
from plan_tool.run_log import ClaudeCallEnd, hash_prompt, utc_now_iso
from plan_tool.schema import (
    ChangeType,
    Plan,
    PlanStatus,
    Step,
    StepScope,
    StepStatus,
)
from plan_tool.shell import (
    DEFAULT_MAX_TRANSIENT_RETRIES,
    DEFAULT_TRANSIENT_BASE_DELAY,
    get_active_notifier,
)

if TYPE_CHECKING:
    from plan_tool.run_log import RunLogWriter


# ContextVars used to plumb a ``RunLogWriter`` and a sibling-log
# directory through the bare ``Invoker = Callable[[str], tuple[int, str]]``
# interface. ``run_step`` sets these around its ``invoker(prompt)`` call
# so the production :func:`shell_invoker` can read them and forward to
# :func:`_run_streaming_once` (which accepts both as kwargs). Test
# invokers and out-of-tree callers ignore them — the contextvar default
# is ``None`` so a read is always safe.
_run_logger_var: contextvars.ContextVar[Optional["RunLogWriter"]] = (
    contextvars.ContextVar("plan_tool_launcher_run_logger", default=None)
)
_sibling_log_dir_var: contextvars.ContextVar[Optional[Path]] = (
    contextvars.ContextVar("plan_tool_launcher_sibling_log_dir", default=None)
)
_rate_limit_backend_scope: contextvars.ContextVar[Optional[ExitStack]] = (
    contextvars.ContextVar("plan_tool_launcher_rate_limit_backend_scope", default=None)
)


logger = logging.getLogger(__name__)

Invoker = Callable[[str], tuple[int, str]]


# rc the launcher synthesizes when ``stats.is_error=True`` and the
# subprocess exited 0; downstream branches treat it identically to a
# genuine non-zero exit. Lines up with POSIX convention and the existing
# ``if exit_code != 0:`` test so no consumer needs to learn a new sentinel.
_IS_ERROR_RC = 1


# ``ClaudeRunStats`` is defined in :mod:`plan_tool.backend` (the import
# leaf below this module) and re-exported via the module-top import so
# the ~15 ``from plan_tool.launcher import ClaudeRunStats`` sites and
# bare-name references in ``shell_invoker`` / ``run_step`` resolve
# unchanged.

# Modes that mutate plan state (mark step done, advance). All other modes
# are read-only inspections that render a prompt and leave the plan alone.
# Known read-only/review-class modes today: "check",
# "detail-reconcile" (plan/detail audit against code, plan-edit applies),
# "run-reconcile" (code audit against plan, code-edit applies inline via
# ``acceptEdits``), "optimize", "document", "test", "security", "lint".
# Adding a new mode? Decide whether it should advance step state and
# either add to this set or (the usual case) leave it out so ``run_step``
# short-circuits the advance/mark-done branch.
MUTATING_MODES = frozenset({"run"})

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")
_SUMMARY_RE = re.compile(r"^##\s*Summary\s*\n+(.+?)(?:\n|$)", re.MULTILINE)
_FINDINGS_HEADING_RE = FINDINGS_RESPONSE_CONTRACT.heading_pattern()
# Bullets prefixed by an UPPERCASE severity token followed by `:`. The
# leading `-` / `*` is the only allowed bullet marker; we keep the regex
# narrow so prose like "Note: CRITICAL bugs are…" doesn't masquerade as
# a finding.
_FINDING_BULLET_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?(CRITICAL|HIGH|MEDIUM|NIT|LOW)(?:\*\*)?\s*[:\-]",
    re.MULTILINE,
)
# Misshape ``- HIGH `[anchor]`: prose`` — severity token present but the
# well-formed ``:``/``-`` cue is missing (an opening ``[`` sits there
# instead). Treated as a bullet boundary so it is not absorbed into the
# previous finding's body; Decision-block rows (``- **Intent**: …``) do
# not match. Severity is taken from the token; the body keeps the slug
# for anchor recovery downstream.
_MISSHAPED_FINDING_BULLET_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?(?P<sev>CRITICAL|HIGH|MEDIUM|NIT|LOW)(?:\*\*)?\s*"
    r"(?=(?:(?:\*\*|`)*)\[)",
    re.MULTILINE | re.IGNORECASE,
)
_MISSHAPED_FINDING_PREFIX_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?(?:CRITICAL|HIGH|MEDIUM|NIT|LOW)(?:\*\*)?\s*",
    re.IGNORECASE,
)
# Any bullet under the Findings heading that doesn't start with a known
# severity token. Used to bucket "claude formatted oddly" output rather
# than failing the run on a contract miss.
_ANY_BULLET_RE = re.compile(r"^\s*[-*]\s+\S", re.MULTILINE)
_NONE_MARKER_RE = re.compile(
    r"_\(\s*none\s*\)_|^\s*\(\s*none\s*\)\s*$", re.IGNORECASE | re.MULTILINE
)


# Severities the parser recognizes. ``LOW`` is folded into ``MEDIUM`` for
# the per-step verdict line — the security prompt is the only one that
# uses ``LOW``, and the verdict already has too many buckets to add a
# fifth without making it noisy. The raw count is preserved internally
# in case we want it later.
_SEVERITY_TOKENS = ("CRITICAL", "HIGH", "MEDIUM", "NIT")


@dataclass(frozen=True)
class FindingsSummary:
    """Per-step finding counts extracted from a claude review-mode response.

    ``parsed`` is True when a ``## Findings`` block was located; False when
    no block was emitted (treated as 0 critical for exit-code rollup, but
    the per-step verdict line surfaces the contract miss). ``unspecified``
    counts bullets that appeared under the heading but didn't begin with a
    known severity token — surfaced separately so users can see claude
    formatted oddly without failing the run.
    """

    parsed: bool
    counts: dict[str, int]
    unspecified: int

    @property
    def critical(self) -> int:
        return self.counts.get("CRITICAL", 0)

    @property
    def total(self) -> int:
        return sum(self.counts.values()) + self.unspecified


@dataclass(frozen=True)
class FindingBullet:
    """One bullet extracted from a claude ``## Findings`` block.

    ``severity`` is one of ``CRITICAL`` / ``HIGH`` / ``MEDIUM`` / ``NIT`` /
    ``LOW`` (folded to ``MEDIUM`` for downstream consumers that want the
    four-bucket scale; the raw token is preserved for callers that care).
    Bullets without a recognized severity token surface with severity
    ``"UNSPECIFIED"`` so the walk feature can show them rather than
    silently dropping them.
    """

    severity: str
    body: str  # the bullet text after the severity token + colon


def parse_finding_bullets(stdout: str) -> list[FindingBullet]:
    """Extract individual bullets from the last ``## Findings`` block.

    Companion to :func:`summarize_findings` — same anchoring (last
    heading wins, ANSI-stripped) but returns the actual bullets so
    callers like the reconcile-plan-walk feature can show them to the user.

    Bullets matching ``_FINDING_BULLET_RE`` are tagged with their
    severity token; misshaped finding-shaped lines (severity token +
    ``[anchor]`` cue without the well-formed ``:``/``-`` separator) are
    minted as their own bullets so they are not absorbed into a prior
    finding; any freestanding non-finding bullet *before* the first
    severity/misshape start is returned with severity ``"UNSPECIFIED"``.
    Returns ``[]`` when no Findings block is present, when the block is
    empty, or when the block contains the ``_(none)_`` marker.

    Each ``FindingBullet.body`` spans from its own bullet start to the
    next severity/misshape start (or end of block), so trailing content
    — notably a ``## Decision`` sub-block emitted by the reconcile
    prompt — stays attached to the finding it describes instead of
    leaking out as unspecified bullets or vanishing when downstream
    code reads ``bullet.body``.
    """
    clean = _ANSI_RE.sub("", stdout)
    matches = list(_FINDINGS_HEADING_RE.finditer(clean))
    if not matches:
        return []
    block = clean[matches[-1].end():]
    if _NONE_MARKER_RE.search(block):
        return []

    # Boundaries: well-formed severity bullets + misshaped finding lines.
    starts: list[tuple[int, str]] = [
        (m.start(), m.group(1).upper())
        for m in _FINDING_BULLET_RE.finditer(block)
    ]
    well_formed_at = {pos for pos, _ in starts}
    for m in _MISSHAPED_FINDING_BULLET_RE.finditer(block):
        if m.start() in well_formed_at:
            continue
        starts.append((m.start(), m.group("sev").upper()))
    starts.sort(key=lambda item: item[0])

    bullets: list[FindingBullet] = []
    if starts:
        boundaries = [s for s, _ in starts] + [len(block)]
        for (start, severity), end in zip(starts, boundaries[1:]):
            chunk = block[start:end]
            if _FINDING_BULLET_RE.match(chunk):
                # Strip the leading `- SEVERITY:` / `- SEVERITY -` prefix.
                chunk = re.sub(
                    r"^\s*[-*]\s*(?:\*\*)?(CRITICAL|HIGH|MEDIUM|NIT|LOW)"
                    r"(?:\*\*)?\s*[:\-]\s*",
                    "",
                    chunk,
                    count=1,
                )
            else:
                # Misshape: strip `- SEVERITY` only; leave ``[anchor]`` in
                # the body for downstream key recovery.
                chunk = _MISSHAPED_FINDING_PREFIX_RE.sub("", chunk, count=1)
            body = chunk.rstrip()
            if body:
                bullets.append(FindingBullet(severity=severity, body=body))

    # Unspecified bullets: freestanding ``- foo`` lines *before* the
    # first severity/misshape start. Decision-block rows and misshapes
    # after a start stay absorbed or minted above — never harvested here.
    head_end = starts[0][0] if starts else len(block)
    head = block[:head_end]
    for line in head.splitlines():
        if not _ANY_BULLET_RE.match(line):
            continue
        if _FINDING_BULLET_RE.match(line):
            continue
        if _MISSHAPED_FINDING_BULLET_RE.match(line):
            continue
        body = re.sub(r"^\s*[-*]\s+", "", line).strip()
        if body:
            bullets.append(FindingBullet(severity="UNSPECIFIED", body=body))
    return bullets


def findings_output_is_valid(stdout: str) -> bool:
    """Whether the final findings block is usable as outcome evidence.

    A missing/empty/malformed block is intentionally not equivalent to a
    clean audit. Only the explicit ``_(none)_`` sentinel or one or more
    severity-labelled finding bullets establishes a parseable outcome.
    """
    clean = _ANSI_RE.sub("", stdout)
    matches = list(_FINDINGS_HEADING_RE.finditer(clean))
    if not matches:
        return False
    block = clean[matches[-1].end():]
    if _NONE_MARKER_RE.search(block):
        return True
    bullets = parse_finding_bullets(stdout)
    return bool(bullets) and all(bullet.severity != "UNSPECIFIED" for bullet in bullets)


def summarize_findings(stdout: str) -> FindingsSummary:
    """Extract severity counts from the last ``## Findings`` block.

    Anchors to the *last* ``## Findings`` heading so a verbose-stream
    echo of the prompt earlier in the buffer doesn't confuse the parser.
    Strips ANSI codes first since ``shell_invoker`` runs claude with
    ``--verbose``, which can interleave color codes.

    Three branches:
      - No heading found → ``parsed=False``, all counts zero. Caller emits
        a "could not summarize" verdict but still treats the run as
        passing for exit-code purposes.
      - Heading found, ``_(none)_`` marker present → counts all zero,
        ``parsed=True``. Empty findings block; passes.
      - Heading found, bullets present → count by severity token. Bullets
        without a known token bucket into ``unspecified``.
    """
    clean = _ANSI_RE.sub("", stdout)
    matches = list(_FINDINGS_HEADING_RE.finditer(clean))
    if not matches:
        return FindingsSummary(parsed=False, counts={}, unspecified=0)
    block = clean[matches[-1].end():]

    counts: dict[str, int] = {tok: 0 for tok in _SEVERITY_TOKENS}
    if _NONE_MARKER_RE.search(block):
        return FindingsSummary(parsed=True, counts=counts, unspecified=0)

    severity_bullets = 0
    sev_positions = []
    for m in _FINDING_BULLET_RE.finditer(block):
        sev_positions.append(m.start())
        token = m.group(1).upper()
        if token == "LOW":
            # Fold LOW into MEDIUM for the verdict — see _SEVERITY_TOKENS.
            token = "MEDIUM"
        counts[token] = counts.get(token, 0) + 1
        severity_bullets += 1

    # Only count freestanding bullets that appear *before* the first
    # severity bullet as unspecified. Bullets that fall inside a
    # severity bullet's chunk — notably the ``- **Intent**: ...`` rows
    # under a ``## Decision`` sub-block — are part of that finding's
    # body and would otherwise inflate the unspecified bucket. When
    # there are no severity bullets at all, every bullet under the
    # heading is unspecified.
    head_end = sev_positions[0] if sev_positions else len(block)
    head = block[:head_end]
    unspecified = sum(1 for _ in _ANY_BULLET_RE.finditer(head))
    return FindingsSummary(parsed=True, counts=counts, unspecified=unspecified)


def format_findings_verdict(step_id: int, summary: FindingsSummary) -> str:
    """One-line verdict: ``Step N — 0 critical / 1 high / 0 medium / 2 nits`` etc.

    Returns a "could not summarize" line when ``summary.parsed`` is False
    so the user sees the contract miss without the run failing.
    """
    if not summary.parsed:
        return f"Step {step_id} — could not summarize (no findings block)"
    parts = [
        f"{summary.counts.get('CRITICAL', 0)} critical",
        f"{summary.counts.get('HIGH', 0)} high",
        f"{summary.counts.get('MEDIUM', 0)} medium",
        f"{summary.counts.get('NIT', 0)} nits",
    ]
    if summary.unspecified:
        parts.append(f"{summary.unspecified} unspecified")
    return f"Step {step_id} — " + " / ".join(parts)


@dataclass
class RunResult:
    step_id: int
    exit_code: int
    advanced_to: Optional[int]  # step id that became `current` after success, if any.
    done: bool  # True when the step was marked DONE.
    stdout: str = ""
    step_title: str = ""
    plan_completed: bool = False  # True when this step took the plan to M/M done.


class LauncherError(Exception):
    """Raised for launcher-level problems: no runnable step, unknown step id, etc."""


def _reject_unmatched_plan_fence(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
        raise LauncherError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before running this plan."
        )


def _notify_or_print(message: str, *, kind: str) -> None:
    """Route an in-flight retry/wait advisory through the live progress line
    when ``run_step`` has one open (so it clears the heartbeat tick first),
    else fall back to the historical ``plan-tool: <message>`` stderr line."""
    notifier = get_active_notifier()
    if notifier is not None:
        notifier.notice(message, kind=kind)
    else:
        print(f"plan-tool: {message}", file=sys.stderr)


def _streaming_prompt_bytes(prompt: str) -> int:
    """Bytes of the prompt payload as the active streaming backend carries it."""
    return get_active_backend().streaming_transport(prompt).prompt_bytes


# The ``run`` prompt embeds the step's entire detail file uncapped, so it is the
# largest per-step prompt the tool assembles — the surface/remedies the advisory
# names when a step's prompt eats the window.
_RUN_BUDGET_SURFACE = "run step"
_RUN_BUDGET_REMEDIES = (
    "plan-tool split",
    "plan-tool scope-out",
    "trim the step's detail file",
)


def _print_run_budget_breakdown(
    step: Step, budget: PromptBudget, *, stream: Optional[TextIO] = None
) -> None:
    """Print one step's prompt-budget breakdown for ``run --dry-run``.

    Inspection only: prints at **every** level (including ``ok``) to stderr, so a
    piped ``run --dry-run`` still yields a clean prompt on stdout while the
    operator sees the headroom breakdown on the terminal. Records no telemetry
    (dry-run sends nothing).
    """
    out = stream if stream is not None else sys.stderr
    print(
        render_budget_summary(
            budget,
            surface=f"run step {step.id}",
            blocks_label="blocks",
            max_blocks=None,
        ),
        file=out,
    )


def _can_prompt_on_rate_limit() -> bool:
    """True when the launcher can safely ask an operator what to do."""
    return (
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stderr, "isatty", lambda: False)()
    )


def _select_rate_limit_backend(name: str) -> bool:
    """Select a fallback backend for the caller-owned recovery scope."""
    backend_scope = _rate_limit_backend_scope.get()
    if backend_scope is None:
        _notify_or_print(
            "no active backend switch scope; waiting instead",
            kind="info",
        )
        return False
    repo_root = get_active_spawn_cwd() or Path.cwd()
    try:
        scoped_selection = scoped_select_active_backend(
            name,
            repo_root=repo_root,
            fallback_factory=model_specs.synthesize_model_family_backend,
            known_override_names=model_specs.model_family_backend_names(),
        )
        selection = scoped_selection.__enter__()
    except (BackendConfigError, ValueError) as exc:
        _notify_or_print(str(exc), kind="info")
        return False
    known_names = set(registered_names()) | model_specs.model_family_backend_names()
    for key in getattr(selection, "unknown_override_names", ()):
        _notify_or_print(
            unknown_backend_override_warning(key, known_names), kind="info"
        )
    effective_backend = getattr(selection, "effective", get_active_backend())
    if shutil.which(effective_backend.binary) is None:
        scoped_selection.__exit__(None, None, None)
        _notify_or_print(
            f"`{effective_backend.binary}` executable not found on PATH",
            kind="info",
        )
        return False
    selected_backend = getattr(selection, "selected", None)
    if selected_backend is not None and selected_backend.name not in registered_names():
        _notify_or_print(
            provisional_backend_warning(selected_backend.name),
            kind="info",
        )
    backend_scope.callback(scoped_selection.__exit__, None, None, None)
    return True


def _ask_rate_limit_action() -> OnRateLimitAction:
    """Ask for a rate-limit action, rejecting same-backend switches here."""
    while True:
        current_backend_name = get_active_backend().name
        choice = ask_on_rate_limit_action(
            current_backend_name=current_backend_name
        )
        if (
            choice.action is OnRateLimitAction.SWITCH
            and choice.switch_backend_name == current_backend_name
        ):
            _notify_or_print(
                f"{current_backend_name} is already active; "
                "choose a different backend",
                kind="info",
            )
            continue
        if choice.action is OnRateLimitAction.SWITCH:
            if _select_rate_limit_backend(choice.switch_backend_name or ""):
                return OnRateLimitAction.SWITCH
            continue
        return choice.action


_thread_stats = threading.local()


def shell_invoker(
    prompt: str,
    *,
    wait_on_rate_limit: Optional[bool] = None,
    max_transient_retries: int = DEFAULT_MAX_TRANSIENT_RETRIES,
    transient_base_delay: float = DEFAULT_TRANSIENT_BASE_DELAY,
    _sleep: Callable[[float], None] = time.sleep,
    _clock: Callable[[], float] = time.time,
) -> tuple[int, str]:
    """Production invoker: `claude -p --verbose --permission-mode acceptEdits <prompt>`.

    Streams stdout *and* stderr to the terminal while accumulating both
    for summary extraction and failure classification (rate-limit
    detection needs both streams since Claude can surface quota copy
    on either).

    Each call is a fresh Claude session with only this prompt in
    context. On non-zero exit the failure is classified via
    :mod:`plan_tool.claude_errors`; rate-limit and transient failures
    are retried inline (the user sees the countdown / backoff on
    stderr). Context-overflow surfaces a hint but is not retried.

    ``wait_on_rate_limit`` defaults to None, which means "honor the
    process-wide on-rate-limit policy" (set by ``cli.main`` from
    ``--on-rate-limit`` / ``--fallback-backend``). Pass True/False
    explicitly to override on a per-call basis (True → WAIT, False → STOP).
    """
    policy = resolve_on_rate_limit_policy(wait_on_rate_limit)
    recover_rate_limit = policy.action is not OnRateLimitAction.STOP
    # ContextVar plumbing: ``run_step`` sets these around its
    # ``invoker(prompt)`` call so we can forward them to
    # ``_run_streaming_once`` without widening the ``Invoker`` Protocol.
    # Out-of-tree callers (tests, direct shell_invoker users) see the
    # default ``None`` and behave exactly as before.
    run_logger = _run_logger_var.get()
    sibling_log_dir = _sibling_log_dir_var.get()
    # Reset the sentinel before the call so an exception (or any path
    # that returns without reaching the assignment below) cannot leak
    # stats from a prior invoker call into the next ClaudeCallEnd.
    shell_invoker._last_stats = ClaudeRunStats()  # type: ignore[attr-defined]
    _thread_stats.stats = shell_invoker._last_stats  # type: ignore[attr-defined]

    # Partial-mutation retry guard (BUG_BACKLOG RISK), shared with ``shell``'s
    # batch path — see :mod:`plan_tool.git_state` for the contract and why both
    # callers need it. ``None`` (no spawn cwd, non-git tree, or a repo
    # unreadable at entry) leaves the loop on its always-retry default, so
    # out-of-tree callers retry exactly as before. The reader is routed through
    # this module's ``_git_changed_paths_or_none`` so existing monkeypatches of
    # that name stay live.
    retry_guard = make_partial_mutation_retry_guard(
        get_active_spawn_cwd(),
        read_changed=lambda p: _git_changed_paths_or_none(p),
    )

    # Seams handed to the shared recovery loop (``rate_limit_loop.py``). The
    # loop owns the 429 / SWITCH / ASK / wait / transient-backoff cascade;
    # launcher supplies the streaming attempt + type-narrowing adapters onto
    # the leaf's neutral vocabulary. See docs/how-to/pipeline/run.md.
    # One-slot cell recording the attempt number `run_once` was most
    # recently called with — see shell.claude_invoke's identical cell for
    # why the wait/sleep seams must derive `next_attempt` from this rather
    # than counting their own calls. ``shell_invoker`` always starts its
    # recovery loop at attempt 1 (no ``attempt`` kwarg of its own), so the
    # cell is seeded the same way.
    _attempt_cell = {"value": 1}

    def _next_attempt() -> int:
        return _attempt_cell["value"] + 1

    def _run_once_seam(attempt_number: int):
        _attempt_cell["value"] = attempt_number
        # Bare in-module reference so ``launcher._run_streaming_once``
        # monkeypatches (TestShellInvokerContextVarPlumbing) are honored.
        try:
            rc, stdout_text, stderr_text, stats = _run_streaming_once(
                prompt,
                run_logger=run_logger,
                attempt=attempt_number,
                sibling_log_dir=sibling_log_dir,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # noqa: BLE001 — classify runner failures
            failure_detail = f"{type(exc).__name__}: {exc}"
            rc, stdout_text, stderr_text, stats = (
                _IS_ERROR_RC,
                failure_detail,
                failure_detail,
                ClaudeRunStats(),
            )
        # Stash on the function object on *every* call so ``run_step`` reads
        # the most recent run's usage without widening the ``Invoker``
        # Protocol. The attribute is initialized at module load below.
        shell_invoker._last_stats = stats  # type: ignore[attr-defined]
        _thread_stats.stats = stats
        return rc, stdout_text, stderr_text

    def _ask_action_seam() -> RecoveryAction:
        return ACTION_TO_RECOVERY[_ask_rate_limit_action()]

    quota_pattern_miss_observer = make_plan_quota_pattern_miss_observer(
        repo_root=get_active_spawn_cwd,
        phase="claude_call",
        notify=_notify_or_print,
    )

    with ExitStack() as backend_scope:
        scope_token = _rate_limit_backend_scope.set(backend_scope)
        try:
            return run_with_rate_limit_recovery(
                run_once=_run_once_seam,
                classify=build_streaming_classification_from_outcome,
                on_nonsuccess=quota_pattern_miss_observer,
                notify=_notify_or_print,
                select_backend=_select_rate_limit_backend,
                ask_action=_ask_action_seam,
                can_prompt=_can_prompt_on_rate_limit,
                wait=make_backend_recovery_wait_seam(
                    _sleep,
                    _clock,
                    writer=lambda: run_logger,
                    next_attempt=_next_attempt,
                    backend_name=lambda: get_active_backend().name,
                    phase="claude_call",
                ),
                prompt_lock=RATE_LIMIT_PROMPT_LOCK,
                current_backend_name=lambda: get_active_backend().name,
                recover_rate_limit=recover_rate_limit,
                action=ACTION_TO_RECOVERY[policy.action],
                fallback_backend=policy.fallback_backend,
                fallback_seconds=DEFAULT_RATE_LIMIT_FALLBACK_SECONDS,
                max_wait_seconds=MAX_RATE_LIMIT_WAIT_SECONDS,
                max_transient_retries=max_transient_retries,
                transient_base_delay=transient_base_delay,
                attempt=1,
                sleep=make_backend_recovery_sleep_seam(
                    _sleep,
                    writer=lambda: run_logger,
                    next_attempt=_next_attempt,
                    backend_name=lambda: get_active_backend().name,
                    phase="claude_call",
                ),
                clock=_clock,
                retry_guard=retry_guard,
            )
        finally:
            _rate_limit_backend_scope.reset(scope_token)


def _run_streaming_once(
    prompt: str,
    *,
    run_logger: Optional["RunLogWriter"] = None,
    phase: str = "claude_call",
    attempt: int = 1,
    sibling_log_dir: Optional[Path] = None,
) -> tuple[int, str, str, "ClaudeRunStats"]:
    """Run one streaming backend call with the active backend's transport.

    Thin wrapper over :func:`plan_tool.backend_runner.run_streaming_once`
    (the Popen supervisor's home): the run lane always carries the prompt
    over the active backend's ``streaming_transport``, so this is where
    that selection is made. Kept at module scope under this name because
    ``shell_invoker`` calls it as a bare in-module reference — a
    ``monkeypatch.setattr(launcher, "_run_streaming_once", fake)`` seam
    tests rely on.
    """
    return run_streaming_once(
        prompt,
        get_active_backend().streaming_transport,
        run_logger=run_logger,
        phase=phase,
        attempt=attempt,
        sibling_log_dir=sibling_log_dir,
    )


# Sentinel attribute: callers in ``run_step`` (step 3) read
# ``shell_invoker._last_stats`` to recover the ``ClaudeRunStats`` for
# the last call without widening the ``Invoker`` Protocol. Initialized
# here so the read is always safe even before any call has happened.
shell_invoker._last_stats = ClaudeRunStats()  # type: ignore[attr-defined]


def _invoker_stats(invoker: Any) -> ClaudeRunStats:
    """Stats of the calling thread's last ``shell_invoker`` call.

    ``completeness-apply --jobs N`` workers share ``shell_invoker``, so its
    ``_last_stats`` attribute can hold another worker's call; the thread-local
    copy cannot. Other invokers (test fakes) keep the attribute read.
    """
    if invoker is shell_invoker:
        local = getattr(_thread_stats, "stats", None)
        if local is not None:
            return local
    return getattr(invoker, "_last_stats", ClaudeRunStats())


def extract_summary(
    stdout: str,
    *,
    final_text: Optional[str] = None,
    full_stdout_scan: bool = False,
) -> Optional[str]:
    """Extract the one-line summary from Claude's stdout.

    Looks for a `## Summary` section and returns the first non-empty line
    after it, truncated to 500 characters. Returns None if not found.

    By default the raw-stdout fallback only scans the last 4 KB — enough
    for the streaming flows that always carry a clean ``final_text``. Set
    ``full_stdout_scan=True`` when no ``final_text`` is available and the
    response may bury the ``## Summary`` block under tool-use chatter
    (e.g. ``apply_finding`` runs in ``acceptEdits`` mode, whose edit-tool
    output can push the summary past the tail window). This keeps summary
    parsing symmetric with :func:`parse_apply_verdict`, which already
    scans the full buffer. ``final_text`` still takes precedence when
    present.

    The cap is generous on purpose: this summary is the full status note
    for non-APPLIED verdicts (e.g. a BLOCKED finding's "why / what to do
    next"), persisted verbatim into the completeness report. Live status
    lines re-clip it short at their own call sites (e.g. `[:80]`), so a
    long note here doesn't bloat terminal output. The 500-char ceiling
    only exists to bound a pathological multi-line blob from a
    misbehaving model.

    When ``final_text`` is supplied (the post-tool ``result`` envelope
    text from :class:`ClaudeRunStats`), it's used as the haystack instead
    of the last 4 KB of raw stdout. The result envelope is a cleaner
    source — it excludes tool-use noise, prompt echoes from
    ``--verbose``, and anything Claude emitted before the final answer
    — so a Summary block that would have been buried under verbose
    chatter remains findable. Callers that don't carry stats (test
    fakes, legacy paths) keep the previous behavior via the default
    ``None``. An empty ``final_text`` (the :class:`ClaudeRunStats`
    default when no ``result`` envelope was seen) is treated as no
    final-text supplied, so the function falls back to ``stdout``.
    """
    if final_text:
        haystack = final_text
    elif full_stdout_scan:
        haystack = stdout
    else:
        haystack = stdout[-4096:]
    clean = _ANSI_RE.sub("", haystack)
    m = _SUMMARY_RE.search(clean)
    if not m:
        return None
    stripped = m.group(1).strip()
    if not stripped:
        return None
    return stripped.splitlines()[0][:500]


_FileStamp = tuple[int, Optional[str]]


def _file_stamp(path: Path) -> Optional[_FileStamp]:
    """``(size, sha256)`` for ``path``; digest ``None`` for a non-file.

    mtime is deliberately not part of the stamp: an identical rewrite applied
    no edit, so only size and content decide "unchanged".
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    try:
        with path.open("rb") as fh:
            digest: Optional[str] = hashlib.file_digest(fh, "sha256").hexdigest()
    except OSError:
        digest = None
    return (stat.st_size, digest)


def _snapshot_step_files(
    step: Step, repo_root: Path
) -> dict[str, Optional[_FileStamp]]:
    """Capture ``(size, sha256)`` per declared file, or ``None`` when missing.

    Used as the pre-call half of the post-flight modification check. ``None``
    sentinel means "didn't exist at snapshot time" — comparing ``None`` to a
    populated tuple post-call counts as a modification (file was created),
    matching what users expect for steps that create new files.
    """
    return {f: _file_stamp(repo_root / f) for f in step.all_files}


def _files_unchanged_since(
    snapshot: dict[str, Optional[_FileStamp]],
    step: Step,
    repo_root: Path,
) -> list[str]:
    """Return declared files whose ``(size, sha256)`` matches their snapshot.

    Files that flip between missing/present count as modified. Content, not
    mtime, decides: an identical rewrite is unchanged and a same-size edit is
    not, because an all-unchanged step is blocked ("no edits applied").
    """
    unchanged: list[str] = []
    for f in step.all_files:
        before = snapshot.get(f)
        path = repo_root / f
        try:
            if before is not None and path.stat().st_size != before[0]:
                continue  # size differs: modified, no need to hash
        except OSError:
            pass
        after = _file_stamp(path)
        if after is not None and after[1] is None:
            # A directory or unreadable entry has no content digest; it
            # cannot prove "no edits", so it counts as modified.
            continue
        if before is None and after is None:
            # Still missing: the step claimed this path but nothing created
            # it. Counts as unchanged (a `creates:` entry never written).
            unchanged.append(f)
            continue
        if before is not None and after is not None and before == after:
            # Equal size and digest: rewriting identical bytes applied no edit.
            unchanged.append(f)
    return unchanged


_VALIDATION_RE = re.compile(r"^##\s*Validation\b", re.MULTILINE)


def _run_test_gate(
    command: str,
    repo_root: Path,
    *,
    timeout_s: int = 600,
) -> tuple[int, str]:
    """Run the plan's ``test_command`` after a step's claude call exits 0.

    Returns ``(rc, tail)`` where ``tail`` is the last ~500 chars of
    combined stdout+stderr with ANSI escapes stripped — short enough to
    fit in ``Step.status_note`` when the gate fails. ``rc`` is ``124``
    on timeout (matching coreutils ``timeout``).
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        clean = _ANSI_RE.sub("", raw)
        return 124, f"timeout after {timeout_s}s: {clean[-400:].strip()}"
    except (FileNotFoundError, PermissionError, OSError) as exc:
        # A missing shell, missing test_command script, or any OS-level
        # spawn failure should fail the gate cleanly — not crash
        # ``run_step`` after the mutating claude call has already landed.
        return 127, f"test gate spawn failed: {type(exc).__name__}: {exc}"[:500]
    combined = proc.stdout + proc.stderr
    clean = _ANSI_RE.sub("", combined)
    return proc.returncode, clean[-500:].strip()


def _has_validation_block(
    stdout: str, *, final_text: Optional[str] = None
) -> bool:
    """True when claude included a ``## Validation`` heading in its response.

    Prefer matching against ``final_text`` — the clean result envelope
    from stream-json — when supplied. The raw stdout includes
    ``--verbose`` echoes of the prompt itself (which mentions
    ``## Validation``) plus any tool-use input that quotes the contract,
    so a match anywhere in the buffer is nearly always satisfied and
    defeats the warning. ``final_text`` is the post-tool assistant
    message and is the right place to enforce the prompt contract.

    Falls back to scanning stdout (after ANSI stripping) when
    ``final_text`` is missing — older test fakes and any callsite that
    has not yet been threaded with ``ClaudeRunStats.final_text``.
    """
    if final_text:
        return _VALIDATION_RE.search(final_text) is not None
    return _VALIDATION_RE.search(_ANSI_RE.sub("", stdout)) is not None


def _test_directive(change_type: Optional[ChangeType]) -> str:
    """Render the run-time test directive for ``change_type``.

    Pure, no I/O — the single source of the imperative the ``run`` prompt
    carries to the implementing agent:

    - ``REFACTOR`` and ``FEATURE`` → add or update tests covering the
      behavior the step changes; green before finishing.
    - ``NON_CODE`` and ``None`` → ``""``.

    **The per-type test-*ordering* contract was removed 2026-07-30 — do not
    reintroduce it.** ``REFACTOR`` steps were told to write characterization
    tests that pass *before* the change. A retrospective replay of every refactor
    step in this repo's history against its own pre-change source and found
    81–89% cannot satisfy that for legitimate reasons: a refactor that
    renames or re-shapes what the tests name leaves them unable to import,
    let alone pass, pre-change. Both types now share one directive, and the
    only test claim the tool *enforces* is the one it can actually check —
    :func:`_step_requires_test_authoring`'s gate, that a test file really was
    created or modified.

    The non-empty case leads with a blank-line separator so the directive
    sits clearly apart from whatever ``run.md`` rendered; the empty cases
    append literally nothing, leaving the prompt byte-identical to today.

    The wording is duplicated from (and kept aligned with)
    ``detail._format_tests_directive`` deliberately — importing it across
    the module boundary would create a dependency edge.
    """
    if change_type in (ChangeType.REFACTOR, ChangeType.FEATURE):
        return (
            "\n\n## Tests for this step\n\n"
            "Add or update tests covering the behavior this step changes, "
            "and get them green before finishing. Cover what the step "
            "actually changes — do not pad the roster to satisfy the gate."
        )
    return ""


def _plan_enforces_step_tests(plan: Plan) -> bool:
    """True when the plan opts into test enforcement (``enforce_step_tests``).

    Absent/``None`` reads as off so plans authored before the switch existed
    keep their original directive-free, ungated behavior.
    """
    return bool(getattr(plan, "enforce_step_tests", None))


def _step_test_enforcement_enabled(plan: Plan, step: Step) -> bool:
    """Resolve the effective test-enforcement switch for ``step``.

    A step-level ``enforce_test_authoring`` override wins when set (``True``
    forces enforcement on even in an off plan; ``False`` exempts the step);
    ``None`` inherits the plan-level ``enforce_step_tests`` default. This is
    the single resolver consulted by both the directive append and the gate
    so the two can never disagree about a given step.
    """
    override = getattr(step, "enforce_test_authoring", None)
    if override is not None:
        return bool(override)
    return _plan_enforces_step_tests(plan)


def _step_requires_test_authoring(plan: Plan, step: Step) -> bool:
    """True when the test-authoring gate applies to ``step``.

    The gate fires only when enforcement is on for the step (plan default or
    per-step override, via :func:`_step_test_enforcement_enabled`) *and* the
    step is a ``feature``/``refactor`` change — the two ``change_type`` values
    that carry a test-creation contract. ``non-code`` and unclassified steps
    are never gated.
    """
    if not _step_test_enforcement_enabled(plan, step):
        return False
    return step.change_type in (ChangeType.FEATURE, ChangeType.REFACTOR)


def _git_changed_paths_or_none(repo_root: Path) -> Optional[set[str]]:
    """Launcher-local alias for :func:`git_state.changed_paths_or_none`.

    Kept as a module-level name so tests can monkeypatch the git read at this
    seam; the implementation lives in the leaf both backend callers share.
    """
    return changed_paths_or_none(repo_root)


def _git_changed_paths(repo_root: Path) -> set[str]:
    """Repo-relative changed paths, or an empty set on any git error.

    Thin wrapper over :func:`_git_changed_paths_or_none` (rather than over the
    leaf directly) so the test-authoring gate honors the same monkeypatch seam.
    Callers here treat "can't tell" as "nothing changed" and so never block on
    a non-git tree; the retry-guard fails closed instead.
    """
    changed = _git_changed_paths_or_none(repo_root)
    return changed if changed is not None else set()


def _creates_new_subdir(repo_root: Path, fc: FileCheck) -> bool:
    """True when the file's direct parent is missing but its grandparent exists.

    Distinguishes a step that creates one new subdirectory under an
    existing one (legitimate, common — e.g. a step that writes test
    fixtures under a new ``tests/fixtures/<name>/`` folder) from a path
    with a deeper structural problem (typo above the parent level,
    wrong repo root) — those still surface as ``MISSING_PARENT`` and
    are blocked by the pre-flight gate.

    Conservative on purpose: only single-level new-dir creation is
    auto-allowed. A path like ``foo/bar/baz/file.md`` where ``foo/``
    doesn't exist still fails — that's almost certainly a wrong path.
    """
    abs_path = repo_root / fc.path
    parent = abs_path.parent
    return not parent.exists() and parent.parent.exists()


def _promote_new_subdir_paths(
    file_checks: list[StepFileCheck], repo_root: Path
) -> list[StepFileCheck]:
    """Promote ``MISSING_PARENT`` → ``NEW`` for one-level-new-dir cases.

    Mirrors ``review._promote_missing_parents`` but with the narrower
    "grandparent exists" condition instead of unconditional promotion.
    Used by ``preflight_step_paths`` so a step that legitimately
    creates a new subdirectory under an existing one doesn't require
    ``--allow-missing-parent`` to run.
    """
    promoted: list[StepFileCheck] = []
    for sfc in file_checks:
        new_files = [
            FileCheck(
                path=fc.path,
                status=(
                    FileExistence.NEW
                    if (
                        fc.status == FileExistence.MISSING_PARENT
                        and _creates_new_subdir(repo_root, fc)
                    )
                    else fc.status
                ),
                created=fc.created,
            )
            for fc in sfc.files
        ]
        promoted.append(StepFileCheck(step_id=sfc.step_id, files=new_files))
    return promoted


def preflight_step_paths(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    allow_missing_parent: bool = False,
) -> None:
    """Refuse to invoke claude when the step's declared paths don't resolve.

    Two checks, both reusing primitives from ``review.py`` so the diagnostic
    matches what ``plan-tool reconcile-plan`` would emit for the same plan:

    1. **Per-step file checks.** Any declared file with status
       ``MISSING_PARENT`` (parent dir doesn't exist under ``repo_root``) is a
       broken path the prompt would otherwise embed verbatim. Naming each
       offending file with its absolute path and missing parent gives the
       user enough to either fix the path or override with
       ``--allow-missing-parent``.

    2. **Plan-wide path-style mismatch.** When ≥80% of *all* declared paths
       in the plan resolve to ``MISSING_PARENT``, the plan was almost
       certainly authored against a different repo root. Per-step fixes
       won't help; the user needs ``--repo-root``. Surfaced as a separate
       diagnostic so the message points at the systemic cause rather than
       leaving the user to fix N paths individually.

    **Auto-promotion for new-subdir creation.** Before either check runs,
    any ``MISSING_PARENT`` path whose grandparent exists is promoted to
    ``NEW`` (handled by :func:`_promote_new_subdir_paths`). This covers
    the common "step creates one new subdirectory under an existing one"
    pattern without requiring ``--allow-missing-parent``. The launcher
    announces each new directory on stderr so the user sees what's being
    permitted. Deeper missing chains (e.g. typo at the parent level)
    still trip the gate.

    Step status is **not** part of the gate — re-running a ``done`` step
    has the same path-correctness concern as a first-run ``pending`` one.
    The gate fires for every mode (mutating and review-only); a wrong
    path doesn't become safe just because the prompt says "audit" instead
    of "implement".

    Raises ``LauncherError`` on either failure unless
    ``allow_missing_parent`` is set.
    """
    if allow_missing_parent:
        return

    file_checks_raw = check_file_existence(plan, repo_root)
    file_checks = _promote_new_subdir_paths(file_checks_raw, repo_root)

    # Announce new subdirs the *current step* will create. Other steps'
    # new-subdir cases aren't relevant to this invocation.
    step_raw = next(
        (sc for sc in file_checks_raw if sc.step_id == step.id), None
    )
    if step_raw is not None:
        new_dirs = sorted({
            (repo_root / fc.path).parent
            for fc in step_raw.files
            if fc.status == FileExistence.MISSING_PARENT
            and _creates_new_subdir(repo_root, fc)
        })
        for d in new_dirs:
            # The rendered suffix is literal "/", so keep its prefix POSIX too.
            try:
                rel = d.relative_to(repo_root).as_posix()
            except ValueError:
                rel = d.as_posix()
            print(
                f"plan-tool: step {step.id} will create new directory "
                f"`{rel}/` (parent exists)",
                file=sys.stderr,
            )

    style_hint = detect_path_style_mismatch(file_checks, repo_root)
    if style_hint is not None:
        examples = "\n".join(f"  - {p}" for p in style_hint.examples)
        pct = round(style_hint.ratio * 100)
        raise LauncherError(
            f"plan-wide path issue: {style_hint.missing_count} of "
            f"{style_hint.total} declared file paths don't resolve under "
            f"repo root `{repo_root}` ({pct}% mismatch). "
            "Likely a wrong repo root rather than per-file bugs. Examples:\n"
            f"{examples}\n"
            "Re-run with `--repo-root <correct-path>` or "
            "`--allow-missing-parent` to override."
        )

    step_check = next(
        (sc for sc in file_checks if sc.step_id == step.id), None
    )
    if step_check is None:
        return
    missing = [
        fc for fc in step_check.files
        if fc.status == FileExistence.MISSING_PARENT and not fc.created
    ]
    if not missing:
        return
    lines = [
        f"step {step.id} declared file paths don't resolve under repo "
        f"root `{repo_root}`:"
    ]
    for fc in missing:
        abs_path = repo_root / fc.path
        lines.append(
            f"  - `{fc.path}` (resolved to `{abs_path}`; parent "
            f"`{abs_path.parent}` missing)"
        )
    lines.append(
        "Fix the step's `files:` entries or pass "
        "`--allow-missing-parent` to override."
    )
    raise LauncherError("\n".join(lines))


def resolve_step(plan: Plan, step_id: Optional[int]) -> Step:
    """Pick the step to run.

    Priority:
      1. If `step_id` is given, use that step (must exist).
      2. Otherwise, use the `current` step if one exists.
      3. Otherwise, use the next runnable pending step (deps all done).

    Raises LauncherError if none of the above apply.
    """
    if step_id is not None:
        try:
            return plan.step_by_id(step_id)
        except KeyError as exc:
            raise LauncherError(str(exc)) from exc

    current = plan.current_step()
    if current is not None:
        return current

    nxt = plan.next_runnable_step()
    if nxt is not None:
        return nxt

    raise LauncherError(
        "no runnable step: either every step is done, or the next pending "
        "step's dependencies aren't satisfied"
    )


def mark_done_and_advance(plan: Plan, step: Step) -> Optional[int]:
    """Mark `step` as done; promote the next runnable pending step to `current`.

    Returns the id of the newly-current step, or None if nothing follows or if
    another step is already `current`. Mutates `plan` in place; caller persists
    with `write_plan`.

    Behaviour on out-of-order runs: if the user explicitly ran a step other
    than the current one (e.g. `plan run foo --step 3` while step 2 is current),
    we mark the requested step done but do NOT promote a new current, because
    doing so would produce a two-current state that write_plan's revalidation
    would reject. The previously-current step is left untouched — the user is
    responsible for advancing it separately.

    Completion flip: when this done-mark takes the plan from N/M → M/M (every
    step done, nothing left to promote), the top-level ``status`` is flipped to
    ``PlanStatus.COMPLETED``. That flip is what makes the plan eligible for
    ``plan-tool sweep`` — sweep gates on top-level ``completed`` AND all steps
    done, and nothing else writes that status. Archival stays with sweep (not
    inlined here) so ``run`` doesn't move files out from under an in-flight
    multi-PR ship; the flip alone is enough to surface the plan for sweeping.
    """
    step.status = StepStatus.DONE
    if plan.current_step() is not None:
        # Another step is still current; don't promote anything.
        return None
    nxt = plan.next_runnable_step()
    if nxt is None:
        if plan.all_steps_done:
            plan.status = PlanStatus.COMPLETED
        return None
    nxt.status = StepStatus.CURRENT
    return nxt.id


def _check_acceptable(step: Step) -> None:
    """Raise unless ``step`` is one a failed gate left for a hand fix.

    A failed gate leaves the step ``current`` -- or ``pending`` when it was
    run out of order -- with a ``status_note``; that note is what separates
    it from a mistyped id, which no suite result may certify.
    """
    failed_gate = step.status == StepStatus.PENDING and bool(step.status_note)
    if step.status != StepStatus.CURRENT and not failed_gate:
        raise LauncherError(
            f"step {step.id} is {step.status.value}"
            + ("" if step.status == StepStatus.DONE else " with no failed-gate note")
            + "; --accept certifies the step a failed gate left behind "
            "(run any other step normally)"
        )
    if step.scope != StepScope.COMMITTED:
        raise LauncherError(
            f"step {step.id} is {step.scope.value}, not committed; "
            "--accept certifies committed steps only"
        )


def accept_step(
    plan_path: Path, *, repo_root: Path, step_id: int
) -> RunResult:
    """Certify a hand-fixed step with the gates a backend run would have run.

    Runs ``test_command`` then each step ``gate`` through :func:`_run_test_gate`
    and, only when all pass, applies :func:`mark_done_and_advance`, clears
    ``status_note``, and writes the plan. A refusal or a red gate writes
    nothing. There is no backend call, so the per-call test-authoring gate
    does not apply: the green suite certifies. Raises :class:`LauncherError`
    for a step that cannot be accepted. See docs/how-to/pipeline/run.md.
    """
    plan = parse_plan(plan_path)
    step = resolve_step(plan, step_id)
    _check_acceptable(step)
    if not plan.test_command and not step.gate:
        raise LauncherError(
            f"nothing certifies step {step.id}: the plan has no test_command "
            "and the step has no gate"
        )
    commands = [c for c in [plan.test_command, *step.gate] if c]
    for cmd in commands:
        print(f"\n[accept] running: {cmd}", file=sys.stderr)
        t0 = time.monotonic()
        rc, tail = _run_test_gate(cmd, repo_root)
        if rc != 0:
            print(
                f"[accept] FAILED in {time.monotonic() - t0:.1f}s (rc={rc})\n"
                f"command: {cmd}\n"
                f"tail:\n{tail}\n\n"
                f"ERROR: step {step.id} not accepted; the plan is unchanged.",
                file=sys.stderr,
            )
            return RunResult(
                step_id=step.id, exit_code=rc, advanced_to=None, done=False,
                step_title=step.title,
            )
    # The gates can run for minutes: re-read before the write-back so an edit
    # to the plan made meanwhile survives (as ``run_step`` does).
    wb_plan, wb_step = _reread_plan_for_writeback(
        plan_path, step, in_memory_plan=plan
    )
    # The preconditions were checked on the pre-gate snapshot; check again on
    # the fresh copy, since the plan may have changed while the gates ran.
    _check_acceptable(wb_step)
    advanced_to = mark_done_and_advance(wb_plan, wb_step)
    wb_step.status_note = None
    # Same completion write as a backend-run step, so the lessons log is not
    # left without an entry for it (no model summary exists to record).
    _persist_step_completion(
        plan_path, wb_plan, wb_step, repo_root=repo_root, summary=None,
        rerun_command=f"plan-tool run {plan_path.stem} --step {step.id} --accept",
    )
    return RunResult(
        step_id=step.id,
        exit_code=0,
        advanced_to=advanced_to,
        done=True,
        step_title=step.title,
        plan_completed=wb_plan.status == PlanStatus.COMPLETED,
    )


_LESSONS_STEP_RE = re.compile(r"step\s+(\d+)\s*:", re.IGNORECASE)


def read_lessons_step_ids(path: Path) -> set[int]:
    """Return the set of step ids referenced in a lessons log file.

    Loose regex (``step\\s+(\\d+)\\s*:``) so directly edited entries match
    even when the leading bullet/timestamp differs from
    :func:`append_lesson`'s exact output. Returns an empty set on a
    missing/unreadable file — caller distinguishes "no entries" from
    "no file" via :meth:`Path.exists`.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {int(m.group(1)) for m in _LESSONS_STEP_RE.finditer(text)}


def append_lesson(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    now: Optional[datetime] = None,
    summary: Optional[str] = None,
) -> Optional[Path]:
    """Append a one-line completion entry to the plan's lessons log.

    When `summary` is provided the line includes the takeaway:
        - <ts> step N: <title> — <summary>
    Otherwise falls back to the v0.1 format:
        - <ts> step N: <title>

    No-op when `plan.lessons` is unset. Creates parent directories and the
    lessons file if they don't yet exist. Returns the path written to, or None
    if lessons weren't configured. `now` is injectable for deterministic tests.
    """
    if plan.lessons is None:
        return None
    lessons_path = repo_root / plan.lessons
    # Idempotency guard: a retry after a partial-state persistence
    # failure (lesson committed, plan flip raised) re-enters the
    # success-path tail of ``run_step`` because the plan still reads
    # ``current``. Short-circuit when this step already has an entry so
    # the retry doesn't double-log. Loose ``read_lessons_step_ids``
    # match catches directly edited entries too.
    if lessons_path.is_file() and step.id in read_lessons_step_ids(lessons_path):
        return lessons_path
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    if summary is not None:
        line = f"- {ts} step {step.id}: {step.title} — {summary}\n"
    else:
        line = f"- {ts} step {step.id}: {step.title}\n"
    with lessons_path.open("a", encoding="utf-8") as f:
        f.write(line)
    return lessons_path


def _emit_claude_call_end(
    *,
    invoker: Invoker,
    exit_code: int,
    stdout: str,
    started_monotonic: float,
    phase: str = "claude_call",
    attempt: int = 1,
    stats: Optional[ClaudeRunStats] = None,
) -> None:
    """Construct a :class:`ClaudeCallEnd` and push it to the active shell sink.

    Reads usage / cost / request-id from the invoker's
    ``_last_stats`` sentinel attribute (populated by
    :func:`shell_invoker` from the terminal ``{"type": "result"}``
    envelope; falls back to the dataclass default for invokers that
    don't carry one — most notably the per-test fakes).

    The sink is the one installed by
    :meth:`RunLogWriter.bind_shell_sink`; that closure substitutes the
    writer's ``run_id`` / ``phase`` / ``attempt`` before appending to
    the JSONL, mirroring the path
    :mod:`plan_tool.shell.claude_invoke` already uses. With no sink
    installed (or the sink raising) the call is a no-op — a logging
    failure must not perturb the claude call result.
    """
    from plan_tool import shell as shell_module

    sink = shell_module.get_active_sink()
    if sink is None:
        return
    if stats is None:
        stats = _invoker_stats(invoker)
    # When the subprocess exited cleanly but the terminal ``result``
    # envelope reported ``is_error: true``, synthesize a non-zero rc so
    # the stamped event matches what every downstream rc-bucketed
    # consumer (``runs profile``, success/error analytics) already
    # expects. A genuine non-zero subprocess rc wins — preserving it
    # keeps the bucket honest.
    effective_rc = exit_code if exit_code != 0 else (
        _IS_ERROR_RC if stats.is_error else 0
    )
    event = ClaudeCallEnd(
        ts=utc_now_iso(),
        run_id="",  # overwritten by the bind_shell_sink closure
        phase=phase,
        attempt=attempt,
        rc=effective_rc,
        duration_ms=int((time.monotonic() - started_monotonic) * 1000),
        stdout_bytes=len(stdout.encode("utf-8")),
        tokens_input=stats.tokens_input,
        tokens_output=stats.tokens_output,
        cache_creation_tokens=stats.cache_creation_tokens,
        cache_read_tokens=stats.cache_read_tokens,
        request_id=stats.request_id,
        cost_usd=stats.cost_usd,
        input_includes_cached=stats.input_includes_cached,
    )
    try:
        sink(event)
    except Exception as exc:  # noqa: BLE001 — best-effort, matches shell.py
        print(
            f"warning: run-log sink raised {type(exc).__name__}: {exc}; "
            "claude call result is unaffected",
            file=sys.stderr,
        )


def _invoke_and_log_end(
    invoker: Invoker,
    prompt: str,
    *,
    run_logger: Any,
    started_monotonic: float,
    attempt: int,
) -> tuple[int, str]:
    """Run an ``apply_finding`` call inside its bound sink and write its end.

    The streaming invoker emits no ``claude_call_end`` itself. A raising
    invoker still gets an end (rc 1, no output) so its start is not orphaned.
    """
    def emit(exit_code: int, stdout: str, *, stats: Optional[ClaudeRunStats] = None) -> None:
        # Best-effort: a failed log write must neither mask the invoker's own
        # exception nor turn a completed apply into a restored failure.
        if run_logger is None:
            return
        try:
            _emit_claude_call_end(
                invoker=invoker, exit_code=exit_code, stdout=stdout,
                started_monotonic=started_monotonic,
                phase="apply_finding_dispatch", attempt=attempt, stats=stats,
            )
        except Exception:  # noqa: BLE001
            logger.exception("apply_finding call end could not be written")

    try:
        exit_code, stdout = invoker(prompt)
    except BaseException:
        # A raise carries no usage; the invoker's stats may be a prior call's.
        emit(1, "", stats=ClaudeRunStats())
        raise
    emit(exit_code, stdout)
    return exit_code, stdout


def _persist_step_completion(
    plan_path: Path,
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    summary: Optional[str],
    rerun_command: Optional[str] = None,
) -> None:
    """Append the lesson entry then commit the plan DONE/CURRENT flip.

    Lesson-first ordering closes the transactional gap that the prior
    write_plan→append_lesson order opened: an append_lesson failure now
    leaves the plan unchanged on disk (CURRENT) so a retry re-enters the
    success path safely, and a write_plan failure leaves an idempotent
    lesson entry whose re-write the append_lesson guard absorbs. The
    residual SIGKILL window between the two writes is documented as
    accepted residual risk; this helper does not close it.

    Raises whatever ``append_lesson`` / ``write_plan`` raise after
    emitting a partial-state diagnostic on stderr that names the side
    that did commit, the side that didn't, and the recovery hint.
    """
    lesson_committed = False
    lessons_path: Optional[Path] = None
    rerun = rerun_command or f"plan-tool run --step {step.id}"
    try:
        lessons_path = append_lesson(
            plan, step, repo_root=repo_root, summary=summary
        )
        lesson_committed = True
        write_plan(plan_path, plan)
    except Exception as exc:  # noqa: BLE001 — diagnose any persistence error
        if not lesson_committed:
            committed_side = "neither"
            failed_side = "lessons"
            recovery = (
                f"re-run `{rerun}`; the lesson "
                "append is idempotent and the plan flip will land on retry"
            )
        else:
            committed_side = "lessons"
            failed_side = "plan"
            recovery = (
                f"the lesson entry has already landed at "
                f"`{lessons_path}`; re-run `{rerun}` to retry the plan "
                "write — the idempotent lesson append will skip"
            )
        print(
            f"plan-tool: step {step.id} persistence partial-state — "
            f"{failed_side} write raised "
            f"{type(exc).__name__}: {exc}; "
            f"committed={committed_side}; "
            f"plan_path=`{plan_path}`; "
            f"lessons_path=`{lessons_path}`; "
            f"recovery: {recovery}",
            file=sys.stderr,
        )
        raise


def _reread_plan_for_writeback(
    plan_path: Path, step: Step, *, in_memory_plan: Plan
) -> tuple[Plan, Step]:
    """Re-read the plan from disk for a status write-back.

    ``run_step`` parses the plan once at entry and holds that snapshot
    across the (often multi-minute) claude call. Writing it back
    verbatim silently clobbers any edit the operator — or a concurrent
    process — made to the plan file *during* the call (observed: a
    ``files:`` array rename reverted when a later step's run completed
    and wrote its stale copy). Re-reading immediately before the write
    and re-applying only the step's status transition to the fresh copy
    preserves those edits — everything outside the run step's own status
    fields comes from disk, not from the stale snapshot. The plan file
    isn't a drift-watched path, so this is the only guard against the
    clobber.

    Returns the fresh ``(plan, step)``. Falls back to the in-memory copy
    (with a stderr warning) if the on-disk plan no longer parses or the
    step id is gone — a structural edit mid-run is rare, and landing the
    status flip on the stale copy beats crashing after the step's work
    already succeeded.
    """
    try:
        fresh = parse_plan(plan_path)
        return fresh, fresh.step_by_id(step.id)
    except Exception as exc:  # noqa: BLE001 — any re-read failure → fall back
        warn(
            f"plan file unreadable for status write-back "
            f"({type(exc).__name__}: {exc}); writing step {step.id} "
            f"status from the in-memory copy — re-check the plan after."
        )
        return in_memory_plan, step


def selected_reconcile_plan_fingerprint_changed(plan_path: Path, expected: str) -> bool:
    """True when the plan's current fingerprint doesn't match ``expected``.

    A read/hash failure is treated as a change (fail-closed), matching
    :func:`plan_tool.review_persistence.audit_input_fingerprint_matches_disk`'s
    posture that a bad current input is simply stale.
    """
    try:
        return compute_plan_fingerprint(plan_path) != expected
    except Exception:  # noqa: BLE001 — unreadable now is staler than mismatched
        return True


# ``model_failure_receipt`` reasons ``run`` emits; DATA_CONTRACT.md lists them.
REASON_INVOKE = "invoke"
REASON_NO_EDITS_APPLIED = "no-edits-applied"
REASON_TEST_AUTHORING_GATE = "test-authoring-gate"
REASON_TEST_GATE = "test-gate"
REASON_GATE = "gate"


def _record_step_failure_receipt(
    run_logger: Optional["RunLogWriter"],
    *,
    plan_path: Path,
    step: Step,
    reason: str,
    reply: str,
) -> None:
    """Keep a failed step's final reply in a sidecar and log its receipt."""
    repo_root = getattr(run_logger, "repo_root", None)
    if run_logger is None or repo_root is None:
        return
    sidecar = store_model_response_sidecar(
        repo_root=Path(repo_root),
        # Leading underscore: no create-minted plan slug can collide (see roadmap.py).
        producer_slug=f"_run/{getattr(run_logger, 'slug', None) or plan_path.stem}",
        receipt_identity=(
            f"{getattr(run_logger, 'run_id', 'run')}-step{step.id:02d}-"
            f"{time.time_ns()}"
        ),
        raw_response=reply or None,
    )
    run_logger.model_failure_receipt(
        phase="claude_call",
        attempt=1,
        reason=reason,
        response_bytes=sidecar.response_bytes,
        response_sha256=sidecar.digest,
        sidecar_result=sidecar,
    )


@spawn_cwd_from_repo_root
def run_step(
    plan_path: Path,
    *,
    repo_root: Path,
    step_id: Optional[int] = None,
    mode: str = "run",
    invoker: Invoker = shell_invoker,
    dry_run: bool = False,
    reporter: Optional[ProgressReporter] = None,
    allow_missing_parent: bool = False,
    run_logger: Optional["RunLogWriter"] = None,
    detail_grade: str = GRADE_RUN,
    completed_sibling_context: str = "",
    selected_reconcile_plan_snapshot: Optional[Plan] = None,
    selected_reconcile_plan_fingerprint: Optional[str] = None,
    reject_high_selected_reconcile_budget: bool = False,
) -> RunResult:
    """Resolve + render + invoke + (for mutating modes) persist.

    - Loads the plan from `plan_path`.
    - Picks the step via `resolve_step`.
    - Renders the prompt for `mode`.
    - If `dry_run`, prints the rendered prompt and returns without invoking.
    - Otherwise, calls `invoker(prompt)`.
    - On exit code 0 and mode in MUTATING_MODES, marks the step done, advances,
      and appends a lessons entry (if configured). Review-style modes leave the
      plan untouched.
    - On non-zero exit, leaves the plan untouched regardless of mode.

    Does not raise on non-zero invoker exit codes — the caller decides.

    Progress: a single ``[1/1] step N: <title> (mode=<mode>)`` line lands
    on stderr around the invoker call, with periodic heartbeats during
    long calls and a final ``done in Xs`` / ``FAILED in Xs`` close line.
    The default ``shell_invoker`` *also* streams ``claude --verbose`` to
    stdout — the two channels are independent (verbose on stdout, framing
    on stderr) so neither interferes with the other.

    ``detail_grade`` picks which detail artifact grounds the prompt (see
    :func:`plan_tool.renderer.render_prompt`). It is an *input* axis, not a
    lifecycle one: ``mode`` stays ``"run"`` under every grade, so mark-done,
    advance, the test-order directive, and the test-authoring gate behave
    identically. A non-default grade applies to execution only and is
    rejected with any other mode. A missing or off-contract jira-grade
    artifact raises :class:`LauncherError` during prompt build — before the
    invoker, and before the ``dry_run`` branch.

    ``completed_sibling_context`` is an opt-in ownership block for a fresh
    selected ``run-reconcile`` call. It is rendered verbatim through the
    existing template-variable seam and measured as its own prompt-budget
    block. The empty default keeps every ordinary caller and prompt unchanged.

    ``selected_reconcile_plan_snapshot``/``_fingerprint`` ground a selected
    reconcile in one verified plan read, rechecked before invocation;
    ``reject_high_selected_reconcile_budget`` scopes the high-budget refusal
    to that same path.
    """
    if mode in MUTATING_MODES:
        _reject_unmatched_plan_fence(plan_path)
    if detail_grade != GRADE_RUN and mode != "run":
        raise LauncherError(
            f"--detail-grade {detail_grade} applies to execution only "
            f"(got mode '{mode}'); review and reconcile prompts carry their "
            f"own grounding."
        )

    selected_reconcile_preflight = (
        selected_reconcile_plan_snapshot is not None
        or selected_reconcile_plan_fingerprint is not None
        or reject_high_selected_reconcile_budget
    )
    if selected_reconcile_preflight and mode != "run-reconcile":
        raise LauncherError(
            "selected reconcile preflight applies only to mode 'run-reconcile'"
        )

    if (selected_reconcile_plan_snapshot is None) != (
        selected_reconcile_plan_fingerprint is None
    ):
        raise LauncherError(
            "selected run-reconcile plan snapshot and fingerprint must be "
            "provided together"
        )
    plan = (
        selected_reconcile_plan_snapshot
        if selected_reconcile_plan_snapshot is not None
        else parse_plan(plan_path)
    )
    if (
        reject_high_selected_reconcile_budget
        and selected_reconcile_plan_fingerprint is None
    ):
        raise LauncherError(
            "selected run-reconcile budget refusal requires a plan snapshot"
        )
    step = resolve_step(plan, step_id)

    preflight_step_paths(
        plan,
        step,
        repo_root=repo_root,
        allow_missing_parent=allow_missing_parent,
    )

    # Phase: prompt_build. Times the renderer alone so a slow template
    # regression is visible independently from a slow claude call.
    pb_t0 = time.monotonic()
    pb_outcome = "success"
    if run_logger is not None:
        run_logger.phase_start(
            "prompt_build", step_id=step.id, mode=mode,
        )
    budget_blocks: list[tuple[str, int]] = []
    try:
        prompt = render_prompt(
            plan, step, repo_root=repo_root, mode=mode,
            collect_blocks=budget_blocks,
            plan_path=plan_path, detail_grade=detail_grade,
            extra_vars={"completed_sibling_context": completed_sibling_context},
        )
        if completed_sibling_context:
            budget_blocks.append(
                (
                    "completed sibling context",
                    len(completed_sibling_context.encode("utf-8")),
                )
            )
    except Exception as exc:
        pb_outcome = "error"
        if run_logger is not None:
            run_logger.phase_end(
                "prompt_build",
                duration_ms=int((time.monotonic() - pb_t0) * 1000),
                outcome=pb_outcome,
            )
        if isinstance(exc, DetailGradeError):
            # Re-raise as the launcher's own error so CLI callers report it
            # as rc=2 instead of a traceback. Reached before the invoker and
            # before the ``dry_run`` branch below, so a broken artifact can
            # never reach a backend call.
            raise LauncherError(str(exc)) from exc
        raise
    if run_logger is not None:
        run_logger.phase_end(
            "prompt_build",
            duration_ms=int((time.monotonic() - pb_t0) * 1000),
            outcome=pb_outcome,
        )

    # Append the per-step test directive for mutating
    # ``run`` mode only. Positioned here — after the renderer, before the
    # dry-run print and the claude_call_start event — so ``--dry-run``
    # previews it, the logged ``prompt_bytes`` count includes it, and it
    # rides the actual ``invoker(prompt)`` call. Review-style modes
    # (check/security/reconcile) skip the append and stay directive-free.
    if mode in MUTATING_MODES and _step_test_enforcement_enabled(plan, step):
        prompt += _test_directive(step.change_type)

    # Streaming-transport bytes of the fully assembled prompt (test-order
    # directive included). The single measure shared by the advisory below and
    # the run log's ``claude_call_start`` event, so the two never disagree.
    # Budget blocks were collected during render_prompt above (no second
    # detail/lessons load). The test-order directive appended after the render
    # isn't a content block, so it stays out of the breakdown — as before.
    total_bytes = _streaming_prompt_bytes(prompt)

    if dry_run:
        # Dry-run intentionally emits no claude_call phase pair — no
        # subprocess was launched. The prompt_build pair above already
        # captures the only work that actually happened. Print the budget
        # breakdown to stderr (at every level) for pre-spend inspection so the
        # piped prompt on stdout stays clean; record no telemetry (nothing sent).
        _print_run_budget_breakdown(
            step,
            estimate_prompt_budget(
                total_bytes, context_window=active_context_window(), blocks=budget_blocks
            ),
        )
        print(prompt)
        return RunResult(step_id=step.id, exit_code=0, advanced_to=None, done=False)

    if selected_reconcile_plan_fingerprint is not None:
        if selected_reconcile_plan_fingerprint_changed(
            plan_path, selected_reconcile_plan_fingerprint
        ):
            raise LauncherError(
                "selected run-reconcile plan snapshot changed before backend "
                "invocation; retry the command"
            )
    if reject_high_selected_reconcile_budget:
        # A refusal gate: no window learned during the run, so the verdict does not depend on
        # which calls happened first.
        selected_budget = estimate_prompt_budget(
            total_bytes, context_window=active_context_window(observed=False), blocks=budget_blocks
        )
        if selected_budget.level == "high":
            window_note = " (default)" if selected_budget.window_defaulted else ""
            raise LauncherError(
                "selected run-reconcile prompt budget is high; reduce the "
                f"selected scope and retry (~{selected_budget.estimated_tokens:,} tokens vs "
                f"{selected_budget.context_window:,} window{window_note}, judged against the model "
                "catalog's usable window or the default, not a window learned during this run)"
            )

    if reporter is None:
        reporter = StderrReporter()
    handle = reporter.start_step(
        1, 1, f"step {step.id}: {step.title}{change_type_tag(step.change_type)} (mode={mode})"
    )
    pre_snapshot = (
        _snapshot_step_files(step, repo_root)
        if mode in MUTATING_MODES
        else {}
    )
    # Exclude paths dirty before the call; retain HEAD for committed test edits.
    enforce_step_tests = mode in MUTATING_MODES and _step_requires_test_authoring(
        plan, step
    )
    git_test_baseline = (
        _git_changed_paths(repo_root) if enforce_step_tests else set()
    )
    git_test_head = head_revision(repo_root) if enforce_step_tests else None

    # Pre-send prompt-budget advisory — fires once per invoked step, for every
    # mode that sends (run/check/security/reconcile) and independent of the run
    # logger, right before the invoke. Best-effort by contract; the ``except``
    # is belt-and-suspenders so a slip never blocks the invoke or the return.
    # ``active_context_window()`` → the selected model's window where known, else
    # the leaf's default window.
    try:
        budget = maybe_warn_prompt_budget(
            total_bytes,
            context_window=active_context_window(),
            blocks=budget_blocks,
            surface=_RUN_BUDGET_SURFACE,
            remedies=_RUN_BUDGET_REMEDIES,
        )
        record_prompt_budget(
            repo_root,
            plan_slug=slug_from_filename(plan_path) or "",
            phase="run-step",
            total_bytes=total_bytes,
            advisory=budget.level,
            estimated_tokens=budget.estimated_tokens,
            context_window=budget.context_window,
            headroom_ratio=budget.headroom_ratio,
            blocks=budget.blocks,
        )
    except Exception:
        pass

    # Phase: claude_call. run_step has no retry loop (unlike
    # detail.py), so attempt is always 1 here.
    cc_t0 = time.monotonic()
    if run_logger is not None:
        run_logger.phase_start(
            "claude_call", step_id=step.id, mode=mode,
        )
        run_logger.claude_call_start(
            phase="claude_call",
            attempt=1,
            prompt_bytes=total_bytes,
            prompt_sha256=hash_prompt(prompt),
            step_id=step.id,
        )
        ctx = run_logger.bind_shell_sink(phase="claude_call", attempt=1)
    else:
        ctx = nullcontext()
    # Plumb the writer through the bare ``Invoker(prompt)`` call via a
    # ContextVar so ``shell_invoker`` can forward it to
    # ``_run_streaming_once`` for stream-event emission. The sibling-
    # log-dir ContextVar is declared at module scope but left alone
    # here — whoever knows the sibling directory (today: nothing in
    # ``run_step``; future callers can set it before invoking) seeds
    # it themselves, and ``shell_invoker`` already reads whatever the
    # outer context has bound.
    cv_token_rl = _run_logger_var.set(run_logger)
    start = time.monotonic()
    is_error_synthesized = False
    try:
        with ctx:
            try:
                exit_code, stdout = invoker(prompt)
            except Exception:
                if run_logger is not None:
                    run_logger.phase_end(
                        "claude_call",
                        duration_ms=int((time.monotonic() - cc_t0) * 1000),
                        outcome="error",
                        step_id=step.id,
                    )
                raise
            # Consult ``stats.is_error`` from the terminal ``result``
            # envelope: a claude run that completed the subprocess
            # cleanly (rc == 0) but self-reported failure must not be
            # treated as success. Coerce ``exit_code`` here so every
            # downstream branch — the ``_emit_claude_call_end`` call,
            # the ``phase_end`` outcome/rc, the ``if exit_code != 0:``
            # gate, and the returned ``RunResult.exit_code`` — sees the
            # same synthesized value.
            stats = _invoker_stats(invoker)
            if exit_code == 0 and stats.is_error:
                is_error_synthesized = True
                exit_code = _IS_ERROR_RC
            # Emit a ``ClaudeCallEnd`` event with usage fields pulled from
            # the invoker's ``_last_stats`` sentinel. The
            # ``bind_shell_sink`` closure rewrites the run_id / phase /
            # attempt before writing to JSONL; pushing the event here
            # (rather than relying on ``shell.claude_invoke`` to fire one)
            # is what makes the run log carry token / cache / cost data
            # for ``plan-tool run``, which uses ``shell_invoker`` —
            # not ``shell.claude_invoke``.
            if run_logger is not None:
                _emit_claude_call_end(
                    invoker=invoker,
                    exit_code=exit_code,
                    stdout=stdout,
                    started_monotonic=cc_t0,
                    phase="claude_call",
                    attempt=1,
                )
    finally:
        _run_logger_var.reset(cv_token_rl)
    elapsed = time.monotonic() - start
    if run_logger is not None:
        run_logger.phase_end(
            "claude_call",
            duration_ms=int((time.monotonic() - cc_t0) * 1000),
            outcome=("success" if exit_code == 0 else "error"),
            rc=exit_code,
            step_id=step.id,
        )
    if exit_code != 0:
        backend_name = get_active_backend().name
        if is_error_synthesized:
            reason = (
                f"{backend_name} reported is_error in result envelope "
                "(subprocess exited 0)"
            )
        else:
            reason = f"{backend_name} exited with code {exit_code}"
        handle.fail(elapsed, reason)
        if mode in MUTATING_MODES:
            _record_step_failure_receipt(
                run_logger,
                plan_path=plan_path,
                step=step,
                reason=REASON_INVOKE,
                reply=_invoker_stats(invoker).final_text
                or stdout,
            )
        return RunResult(
            step_id=step.id,
            exit_code=exit_code,
            advanced_to=None,
            done=False,
            stdout=stdout,
            step_title=step.title,
        )
    handle.complete(elapsed, len(stdout.encode("utf-8")))

    if mode not in MUTATING_MODES:
        return RunResult(
            step_id=step.id,
            exit_code=0,
            advanced_to=None,
            done=False,
            stdout=stdout,
            step_title=step.title,
        )

    # Prefer the ``result`` envelope's ``final_text`` over the raw
    # stdout buffer when stream-json captured one — the envelope is the
    # post-tool assistant message, free of ``--verbose`` echoes and
    # tool-use chatter that could otherwise mask a ``## Summary`` block.
    # Test fakes that don't carry a ``_last_stats`` attribute get the
    # default :class:`ClaudeRunStats` (empty ``final_text``), which
    # ``extract_summary`` treats as "fall back to stdout".
    invoker_stats = _invoker_stats(invoker)
    summary = extract_summary(stdout, final_text=invoker_stats.final_text)
    if summary is None:
        # Warn loudly: claude likely skipped the prompt-mandated Summary
        # format. Don't refuse — the step may have succeeded otherwise.
        # The launcher has been logging this at info level since v0.2; the
        # stderr warning here surfaces it where users actually look.
        print(
            f"warning: step {step.id} produced no `## Summary` line "
            "(prompt contract violated; lesson entry will lack a takeaway)",
            file=sys.stderr,
        )
        logger.info("no summary extracted from step %d output; falling back", step.id)

    reply = invoker_stats.final_text or stdout

    # Blocks before the test-authoring gate so an executor that applied
    # nothing is named as such, not as a missing test. See
    # docs/how-to/pipeline/run.md.
    if step.all_files:
        unchanged = _files_unchanged_since(pre_snapshot, step, repo_root)
        if len(unchanged) == len(step.all_files):
            files_list = ", ".join(f"`{f}`" for f in unchanged)
            wb_plan, wb_step = _reread_plan_for_writeback(
                plan_path, step, in_memory_plan=plan
            )
            wb_step.status_note = (
                "no edits applied: none of the step's declared files changed; "
                "step not advanced."
            )
            write_plan(plan_path, wb_plan)
            if plan.test_command or step.gate:
                way_forward = (
                    "If the files already hold the intended content, commit "
                    f"them, then `plan-tool run {plan_path.stem} --step "
                    f"{step.id} --accept` certifies the step with the "
                    "plan's gates."
                )
            else:
                way_forward = (
                    "If the files already hold the intended content, add a "
                    "`test_command:` to the plan or a `gate:` to the step, "
                    f"commit, and run `plan-tool run {plan_path.stem} --step "
                    f"{step.id} --accept` (nothing certifies a step with "
                    "neither), or mark the step done by hand."
                )
            print(
                f"\n[no edits applied] FAILED: step {step.id} changed none of "
                f"its declared files: {files_list}\n"
                f"ERROR: step {step.id} not advanced. Read the executor's final "
                f"reply for why it stopped. {way_forward}",
                file=sys.stderr,
            )
            _record_step_failure_receipt(
                run_logger, plan_path=plan_path, step=step,
                reason=REASON_NO_EDITS_APPLIED, reply=reply,
            )
            return RunResult(
                step_id=step.id,
                exit_code=1,
                advanced_to=None,
                done=False,
                stdout=stdout,
                step_title=step.title,
            )

    if not _has_validation_block(
        stdout, final_text=invoker_stats.final_text
    ):
        print(
            f"warning: step {step.id} response had no `## Validation` "
            "section (prompt contract): claude did not declare what it "
            "tested or would have tested.",
            file=sys.stderr,
        )

    # Blocks advancement when an enforced feature/refactor step created no
    # test file. Runs before test_command/gate: it's the cheap check, and a
    # suite run would otherwise drop __pycache__ under tests/ into the delta.
    # Same re-read → status_note → write_plan → early-return contract as the
    # gates below. Known limit: a porcelain set-difference can't see a step
    # that only re-edits a test left dirty by a prior step (uncommitted
    # `run --all`); `--commit` clears the tree between steps and avoids it.
    if enforce_step_tests:
        changed = _git_changed_paths(repo_root) | committed_changed_paths(
            repo_root, git_test_head
        )
        touched = sorted(
            p for p in changed - git_test_baseline if _is_test_code_path(p)
        )
        if not touched:
            ct = step.change_type.value
            wb_plan, wb_step = _reread_plan_for_writeback(
                plan_path, step, in_memory_plan=plan
            )
            wb_step.status_note = (
                f"test-authoring gate failed: {ct} step created or modified "
                "no test file; step not advanced."
            )
            write_plan(plan_path, wb_plan)
            print(
                f"\n[test-authoring gate] FAILED: step {step.id} is a {ct} "
                "step but no test file (tests/… or __tests__/…, test_*.py, "
                "conftest.py, *.test.ts, *.spec.ts and siblings) was "
                "created or modified during the call.\n"
                f"ERROR: step {step.id} not advanced. Add a unit test and "
                "re-run, exempt this step with `enforce_test_authoring: "
                "false`, or unset `enforce_step_tests` plan-wide. Once the "
                "test you add is committed, `plan-tool run "
                f"{plan_path.stem} --step {step.id} --accept` certifies the "
                "step with the plan's gates (it does not re-check authorship).",
                file=sys.stderr,
            )
            _record_step_failure_receipt(
                run_logger, plan_path=plan_path, step=step,
                reason=REASON_TEST_AUTHORING_GATE, reply=reply,
            )
            return RunResult(
                step_id=step.id,
                exit_code=1,
                advanced_to=None,
                done=False,
                stdout=stdout,
                step_title=step.title,
            )
        print(
            f"[test-authoring gate] passed: {len(touched)} test file(s) "
            f"touched ({', '.join(touched)})",
            file=sys.stderr,
        )

    if plan.test_command:
        print(
            f"\n[test gate] running: {plan.test_command}", file=sys.stderr
        )
        tg_t0 = time.monotonic()
        tg_rc, tg_tail = _run_test_gate(plan.test_command, repo_root)
        tg_elapsed = time.monotonic() - tg_t0
        if tg_rc != 0:
            # Re-read before write-back so a concurrent plan-file edit
            # during the claude call isn't clobbered by the stale
            # snapshot; only this step's status_note is reapplied.
            wb_plan, wb_step = _reread_plan_for_writeback(
                plan_path, step, in_memory_plan=plan
            )
            wb_step.status_note = (
                f"test gate failed (rc={tg_rc}); step not advanced. "
                f"Tail: {tg_tail[:400]}"
            )
            write_plan(plan_path, wb_plan)
            print(
                f"[test gate] FAILED in {tg_elapsed:.1f}s (rc={tg_rc})\n"
                f"command: {plan.test_command}\n"
                f"tail:\n{tg_tail}\n\n"
                f"ERROR: step {step.id} not advanced. Fix the regression "
                f"and re-run; after a hand fix is committed, `plan-tool run "
                f"{plan_path.stem} --step {step.id} --accept` certifies it "
                "without a backend call.",
                file=sys.stderr,
            )
            _record_step_failure_receipt(
                run_logger, plan_path=plan_path, step=step,
                reason=REASON_TEST_GATE, reply=reply,
            )
            return RunResult(
                step_id=step.id,
                exit_code=tg_rc,
                advanced_to=None,
                done=False,
                stdout=stdout,
                step_title=step.title,
            )
        print(
            f"[test gate] passed in {tg_elapsed:.1f}s", file=sys.stderr
        )

    # Per-step `gate` commands — run after the plan-level `test_command`
    # gate passes (or is absent) and before advancement, mirroring the
    # test-gate contract exactly. Each command is an advancement
    # precondition: the first non-zero rc short-circuits the loop, writes
    # a status_note naming the failing command + rc + tail, leaves the
    # step current, and returns the gate's rc as exit_code. An empty
    # `gate` list (the schema default) is a no-op and emits nothing.
    for cmd in step.gate:
        print(f"\n[gate] running: {cmd}", file=sys.stderr)
        g_t0 = time.monotonic()
        g_rc, g_tail = _run_test_gate(cmd, repo_root)
        g_elapsed = time.monotonic() - g_t0
        if g_rc != 0:
            # Re-read before write-back so a concurrent plan-file edit
            # during the claude call isn't clobbered by the stale
            # snapshot; only this step's status_note is reapplied.
            wb_plan, wb_step = _reread_plan_for_writeback(
                plan_path, step, in_memory_plan=plan
            )
            wb_step.status_note = (
                f"gate failed (rc={g_rc}); step not advanced. "
                f"Command: {cmd}\nTail: {g_tail[:400]}"
            )
            write_plan(plan_path, wb_plan)
            print(
                f"[gate] FAILED in {g_elapsed:.1f}s (rc={g_rc})\n"
                f"command: {cmd}\n"
                f"tail:\n{g_tail}\n\n"
                f"ERROR: step {step.id} not advanced. Fix the regression "
                f"and re-run; after a hand fix is committed, `plan-tool run "
                f"{plan_path.stem} --step {step.id} --accept` certifies it "
                "without a backend call.",
                file=sys.stderr,
            )
            _record_step_failure_receipt(
                run_logger, plan_path=plan_path, step=step,
                reason=REASON_GATE, reply=reply,
            )
            return RunResult(
                step_id=step.id,
                exit_code=g_rc,
                advanced_to=None,
                done=False,
                stdout=stdout,
                step_title=step.title,
            )
        print(f"[gate] passed in {g_elapsed:.1f}s", file=sys.stderr)

    # Post-flight `creates:` check — advisory, symmetrical with the
    # pre-flight missing-detail recommendation in run_cmd. A step whose
    # primary deliverable is its `creates:` list can otherwise be marked
    # done with none of those files on disk (observed live: an
    # executor's permission gate refused the work, the response read as
    # a completion, and the step advanced hollow); review/verify would
    # only catch it later. Warn loudly naming each missing path, but
    # still advance — the executor may have legitimately renamed or
    # consolidated a deliverable, and reconcile owns that judgment.
    missing_creates = [
        p for p in step.creates if not (repo_root / p).exists()
    ]
    if missing_creates:
        listing = "\n".join(f"  - {p}" for p in missing_creates)
        print(
            f"warning: step {step.id} advanced but "
            f"{len(missing_creates)} of its `creates:` entries are "
            f"missing on disk:\n{listing}\n"
            f"The step may have completed hollow (e.g. an executor "
            f"permission refusal). Verify before trusting it: "
            f"plan-tool run {plan_path.stem} --step {step.id} "
            f"--mode check",
            file=sys.stderr,
        )

    # Re-read the plan before the status write-back so a concurrent edit
    # to the plan file during the claude call survives (see
    # _reread_plan_for_writeback). The advance + note-clear apply to the
    # fresh copy; advanced_to / plan_completed are read from it too.
    wb_plan, wb_step = _reread_plan_for_writeback(
        plan_path, step, in_memory_plan=plan
    )
    advanced_to = mark_done_and_advance(wb_plan, wb_step)
    # status_note is ephemeral and scoped to the current status
    # (PLAN_FORMAT): when the status changes, the note must be cleared,
    # not carried over. A prior test-gate refusal writes a "test gate
    # failed (rc=…); step not advanced" note while the step is stuck;
    # now that this re-run advances it to done, drop that stale note in
    # the same write so the done step doesn't assert a failure it no
    # longer has.
    wb_step.status_note = None
    _persist_step_completion(
        plan_path, wb_plan, wb_step,
        repo_root=repo_root, summary=summary,
    )
    return RunResult(
        step_id=step.id,
        exit_code=0,
        advanced_to=advanced_to,
        done=True,
        plan_completed=wb_plan.status == PlanStatus.COMPLETED,
    )


_VERDICT_HEADING_RE = DEEP_VERDICT_RESPONSE_CONTRACT.heading_pattern()
_VERDICT_TOKEN_RE = DEEP_VERDICT_RESPONSE_CONTRACT.token_pattern()


def parse_deep_verdict(stdout: str) -> Optional[str]:
    """Extract PASS/FAIL/UNKNOWN from a deep-reconcile claude response.

    Anchors on the *last* ``## Verdict`` heading (a verbose-stream echo
    of the prompt earlier in the buffer would otherwise win). Strips
    ANSI codes first since ``shell_invoker`` runs claude with
    ``--verbose`` which can interleave color codes.

    Returns ``None`` when no verdict heading is found or no recognized
    token follows it within the next ~200 characters. Caller treats
    ``None`` as ``UNKNOWN`` for rollup purposes — claude ignored the
    contract but may still have produced useful prose, and we don't
    want a contract miss to FAIL the step.
    """
    clean = _ANSI_RE.sub("", stdout)
    matches = list(_VERDICT_HEADING_RE.finditer(clean))
    if not matches:
        return None
    block = clean[matches[-1].end() : matches[-1].end() + 200]
    m = _VERDICT_TOKEN_RE.search(block)
    if m is None:
        return None
    return m.group(1)


# Bullet text injected into the apply-finding prompt's ``## Verdict``
# option list only for opt-in callers (``allow_structural_verdict=True``).
# Kept here, not statically in the prompt, so ``create``'s unedited
# callers never see the option offered (guard (a)).
_STRUCTURAL_VERDICT_OPTION = (
    "- `BLOCKED-STRUCTURAL` — the finding's only correct fix is to split "
    "this step into two type-pure steps (e.g. a mixed refactor + feature). "
    "An apply edit can't do that; a separate split/escalation path handles "
    "it. Emit this instead of `BLOCKED` when splitting is the remedy."
)


# ``BLOCKED-STRUCTURAL`` MUST precede ``BLOCKED``: alternation is
# leftmost-match and ``\bBLOCKED\b`` matches inside ``BLOCKED-STRUCTURAL``
# (the ``-`` is a non-word char, so a word boundary sits after ``D``). If
# ``BLOCKED`` came first the longer token would silently collapse into it.
_APPLY_VERDICT_TOKEN_RE = APPLY_VERDICT_RESPONSE_CONTRACT.token_pattern()


def _apply_verdict_prompt_contract(
    *, allow_structural_verdict: bool
):
    """Return the response shape this apply invocation is allowed to choose."""
    if allow_structural_verdict:
        return APPLY_VERDICT_RESPONSE_CONTRACT
    return APPLY_BASIC_VERDICT_RESPONSE_CONTRACT


def parse_apply_verdict(stdout: str) -> Optional[str]:
    """Extract APPLIED / NOT-APPLICABLE / BLOCKED / BLOCKED-STRUCTURAL
    from an apply-finding claude response.

    Anchors on the *last* ``## Verdict`` heading (verbose stream echoes
    of the prompt earlier in the buffer would otherwise win). Strips
    ANSI codes first.

    Returns ``None`` when no verdict heading is found or no recognized
    token follows it within ~200 characters — caller treats that as
    ``UNKNOWN`` (Claude ignored the contract; we don't trust the run).
    """
    clean = _ANSI_RE.sub("", stdout)
    matches = list(_VERDICT_HEADING_RE.finditer(clean))
    if not matches:
        return None
    block = clean[matches[-1].end() : matches[-1].end() + 200]
    m = _APPLY_VERDICT_TOKEN_RE.search(block)
    if m is None:
        return None
    return m.group(1)


@dataclass(frozen=True)
class ApplyFindingResult:
    """Outcome of one ``apply_finding`` call.

    ``verdict`` is one of ``"APPLIED"`` / ``"NOT-APPLICABLE"`` /
    ``"BLOCKED"`` / ``"BLOCKED-STRUCTURAL"`` / ``"UNKNOWN"`` (the last
    covers Claude exiting non-zero or ignoring the verdict contract).
    ``summary`` is the one-line takeaway extracted from the response.
    ``diff_text`` is a unified diff over the plan file plus the step's
    detail file (when one is declared and exists). ``pre_snapshot``
    carries the pre-invocation contents of every file we tracked, so
    the caller can revert when the user rejects the diff. ``dry_run``
    results carry the rendered prompt in ``prompt`` and otherwise
    leave the diff/summary fields empty.

    ``introduced_findings`` and ``resolved_findings`` capture the
    correctness + completeness delta around the edit: deterministic
    primitives ran against both the pre-state and post-state plan,
    and any IDs new to the post-state are regressions, any IDs
    missing from the post-state are fixes. Both lists are empty for
    dry-run, BLOCKED/BLOCKED-STRUCTURAL/NOT-APPLICABLE/UNKNOWN, and
    clean APPLIED runs.
    """

    step_id: Optional[int]
    exit_code: int
    verdict: str
    summary: str
    diff_text: str
    pre_snapshot: dict[Path, Optional[str]]  # None = file didn't exist
    stdout: str
    prompt: Optional[str] = None
    introduced_findings: tuple = ()
    resolved_findings: tuple = ()
    removed_created_detail_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeferredApplyVerdict:
    """A launcher-classified verdict for a caller that owns persistence.

    ``restoration_succeeded`` is false only when an invocation raised and the
    launcher could not restore every tracked file. Deferred callers must not
    continue or select such an outcome.
    """

    verdict: str
    step_id: int
    restoration_succeeded: bool = True


def _snapshot_text_files(
    paths: list[Path],
) -> dict[Path, Optional[str]]:
    """Read text contents for ``paths``; ``None`` for missing files.

    Used to capture pre-invocation state of the plan + detail file so
    the apply-finding flow can compute a diff and revert on demand.
    """
    out: dict[Path, Optional[str]] = {}
    for p in paths:
        try:
            out[p] = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            out[p] = None
    return out


def _restore_text_files(snapshot: dict[Path, Optional[str]]) -> None:
    """Restore files from ``snapshot``. Files that didn't exist before
    are deleted if they exist now (Claude shouldn't be creating files
    via this prompt, but defend against it)."""
    for path, content in snapshot.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.write_text(content, encoding="utf-8")


def _remove_unauthorized_created_files(
    pre_snapshot: dict[Path, Optional[str]],
) -> tuple[str, ...]:
    """Delete tracked paths absent before apply that exist after an accepted run."""
    removed: list[str] = []
    for path, pre in pre_snapshot.items():
        if pre is None and path.exists():
            path.unlink()
            removed.append(str(path))
    return tuple(removed)


def _restore_text_files_after_invocation_exception(
    snapshot: dict[Path, Optional[str]],
) -> bool:
    """Attempt every restore and report whether all tracked paths succeeded.

    Raised backend invocations must preserve their original exception even when
    restoring one path fails. The ordinary explicit-revert helper remains
    fail-fast so its existing callers retain their behavior.
    """
    restored_all = True
    for path, content in snapshot.items():
        try:
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_text(content, encoding="utf-8")
        except Exception:
            restored_all = False
    return restored_all


def _expose_invocation_restore_status(
    invocation_error: BaseException, restored_all: bool,
) -> None:
    """Expose restore safety to deferred callers without replacing the error."""
    try:
        setattr(invocation_error, "apply_finding_restore_succeeded", restored_all)
    except Exception:
        # Some exception implementations may reject attribute assignment. The
        # original backend exception remains the required host disposition.
        pass


POST_EDIT_PARSE_FAILURE_ID = "post-edit-parse-failure"


def introduced_parse_failure(introduced_findings: Sequence) -> bool:
    """True when ``apply_finding`` flagged a broken post-edit plan."""
    return any(
        getattr(r, "id", None) == POST_EDIT_PARSE_FAILURE_ID
        for r in introduced_findings
    )


def revert_apply_if_parse_broken(result: "ApplyFindingResult") -> bool:
    """Revert ``apply_finding`` edits when they broke YAML/frontmatter parse.

    Returns ``True`` when a revert was performed. Callers should halt
    further applies — an unparseable plan wedges every subsequent
    ``parse_plan`` at loop entry.
    """
    if not introduced_parse_failure(result.introduced_findings):
        return False
    _restore_text_files(result.pre_snapshot)
    return True


def _render_diff(
    pre: dict[Path, Optional[str]],
    post: dict[Path, Optional[str]],
    *,
    repo_root: Path,
) -> str:
    """Build a unified diff string covering each tracked file.

    Empty when nothing changed. Each per-file diff is preceded by the
    repo-relative path so the user can tell which file is which.
    """
    import difflib as _difflib

    chunks: list[str] = []
    for path in pre.keys():
        before = pre.get(path) or ""
        after = post.get(path) or ""
        if before == after:
            continue
        try:
            label = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            label = str(path)
        diff_lines = list(
            _difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{label}",
                tofile=f"b/{label}",
                n=3,
            )
        )
        if diff_lines:
            chunks.append("".join(diff_lines))
    return "\n".join(chunks)


def _format_findings_as_body(findings: tuple) -> str:
    """Bundle one or more deterministic-validation findings into a
    finding body suitable for the apply-finding prompt.

    Single findings include a canonical confidence line. Multi-finding bodies
    prepend a directive and number their confidence-tagged entries so the
    apply-finding prompt can address the complete bundle.
    """
    if not findings:
        return ""
    if len(findings) == 1:
        f = findings[0]
        return format_recommendation_for_apply(f)
    lines = [
        f"The previous edit introduced {len(findings)} new findings. "
        "Address all of them in this single edit.",
        "",
    ]
    for i, f in enumerate(findings, 1):
        severity = severity_label(f.severity)
        lines.append(
            f"### Finding {i}: [{severity}] {f.title} "
            f"[{confidence_label(f.confidence)}]"
        )
        lines.append("")
        lines.append(f.body.strip())
        restated = restated_property_or_none(f)
        if restated:
            lines.append("")
            lines.append(f"{RESTATED_PROPERTY_LABEL}: {restated}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_targeted_fix_block(targeted_fix: Optional[str]) -> str:
    """Render the ``${finding_fix_block}`` injected into apply-finding.

    Returns a ``## Targeted fix`` section quoting the audit's proposed
    edit when one was passed, else ``""`` (the template renders nothing).
    Keeping this a pre-built block — rather than a template conditional —
    lets the prompt stay a plain ``string.Template``.
    """
    fix = (targeted_fix or "").strip()
    if not fix:
        return ""
    return (
        "\n## Targeted fix (realize exactly this intent)\n\n"
        "The audit proposed this remediation as the intended change. "
        "Realize exactly its intent as the plan/detail edit that closes "
        "the finding — stay within it, don't expand scope. It's what the "
        "operator was shown before approving:\n\n"
        f"> {fix}\n"
    )


def _format_feedback_block(operator_feedback: Optional[str]) -> str:
    """Render the ``${operator_feedback_block}`` injected into apply-finding.

    Returns an ``## Operator feedback`` section quoting the steering the
    operator typed at the walk's ``(f)eedback`` prompt, else ``""``. This
    is authoritative direction (not the audit's machine-proposed fix), so
    the block tells Claude to let it refine or override the targeted fix
    where they disagree — while still staying within the finding's scope.
    """
    fb = (operator_feedback or "").strip()
    if not fb:
        return ""
    return (
        "\n## Operator feedback (authoritative — steer the edit by this)\n\n"
        "The operator reviewed this finding and added direction for how to "
        "apply it. Treat it as the authoritative intent: where it refines, "
        "narrows, or overrides the finding (or the targeted fix above), "
        "follow the operator. Make the edit the way they describe; don't "
        "expand beyond it:\n\n"
        f"> {fb}\n"
    )


# Whole-set cap for the advisory carried block in apply-finding. Distinct
# from ``review._CARRIED_BLOCK_MAX_FINDINGS`` (the audit block's cap): the
# apply prompt already carries full plan content, so keep the advisory tail
# modest.
_CARRIED_APPLY_MAX_FINDINGS = 20


def _format_carried_context_block(
    carried: Sequence[CarriedFinding],
    *,
    max_findings: int = _CARRIED_APPLY_MAX_FINDINGS,
) -> str:
    """Render the ``${carried_findings_block}`` injected into apply-finding.

    Strictly advisory: the findings the iterate loop already surfaced/tried
    this run, so the apply avoids re-proposing an already-blocked remedy. It
    does NOT widen what may be edited. Returns ``""`` when empty so the
    template stays a plain ``string.Template``. Kept separate from
    ``review._format_carried_findings_block`` on purpose — different prompt,
    different scope-guard exposure; the slug (the audit loop's dedup
    identity) is meaningless here and is not rendered.
    """
    if not carried:
        return ""
    limit = max(0, max_findings)
    ordered = sorted(
        carried,
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
        "## Already surfaced this run (advisory — context only, "
        "do not act on these)",
        "",
        "These findings were raised earlier in this iterate loop, with",
        "what happened to each. Use them to avoid re-proposing a remedy a",
        "prior finding already established won't land. This is context",
        "only — it does NOT widen what you may edit. Apply only the",
        "finding(s) above and stay inside the plan/detail surface.",
        "",
    ]
    for finding in selected:
        resolution = ""
        if finding.resolution != CARRIED_RESOLUTION_OPEN:
            resolution = f", {finding.resolution}"
            if finding.resolution_reason:
                resolution += f": {finding.resolution_reason}"
        lines.append(
            f"- ({finding.severity.upper()}{resolution}) {finding.title} "
            f"[{confidence_label(finding.confidence)}]"
        )
        if finding.body_excerpt:
            lines.append(f"  {finding.body_excerpt}")
    if dropped:
        lines.append(
            f"… {dropped} more lower-priority finding(s) not shown "
            f"(cap {limit})."
        )
    lines.append("")
    return "\n".join(lines)


def _compute_findings_delta(
    plan_path: Path,
    pre_findings: tuple,
    pre_finding_ids: set,
    *,
    repo_root: Path,
    plan_name: Optional[str],
    step_id: Optional[int],
) -> tuple[tuple, tuple]:
    """Re-run deterministic primitives against the on-disk plan and
    return ``(introduced, resolved)`` against the pre-edit baseline.

    Returns a synthetic ``post-edit-parse-failure`` introduced finding
    when the post-edit plan no longer parses — surfacing that is
    essential because the user shouldn't keep an unparseable plan.
    """
    from plan_tool.review import ReviewError, collect_deterministic_findings

    try:
        post_plan = parse_plan(plan_path)
        post_findings = collect_deterministic_findings(
            post_plan, plan_path, repo_root=repo_root,
            plan_name=plan_name or plan_path.stem,
        )
        post_finding_ids = {r.id for r in post_findings}
        introduced = tuple(
            r for r in post_findings
            if r.id not in pre_finding_ids
        )
        resolved = tuple(
            r for r in pre_findings
            if r.id not in post_finding_ids
        )
        return introduced, resolved
    except ReviewError as exc:
        # collect_deterministic_findings's own unmatched-fence guard raises
        # this — a real defect, but not a YAML/frontmatter parse failure;
        # give it its own accurate diagnosis instead of falling into the
        # generic branch below and telling the user the wrong thing broke.
        from plan_tool.review import Recommendation as _Rec
        introduced = (_Rec(
            id=POST_EDIT_PARSE_FAILURE_ID,
            source="apply-validation",
            severity="critical",
            step_id=step_id,
            title="post-edit plan has an unmatched opening code fence",
            body=(
                f"Claude's edit left the plan with an unmatched opening "
                f"code fence ({exc}). Reverting strongly recommended."
            ),
            suggested_action=None,
        ),)
        return introduced, ()
    except DetailFormatError:
        # A malformed marker written by the model's own edit is a distinct,
        # named refusal — never the generic "plan failed to parse"
        # diagnosis below, which would misreport what actually broke.
        raise
    except UnsupportedPlanFormatVersionError:
        raise
    except Exception:
        from plan_tool.review import Recommendation as _Rec
        introduced = (_Rec(
            id=POST_EDIT_PARSE_FAILURE_ID,
            source="apply-validation",
            severity="critical",
            step_id=step_id,
            title="post-edit plan failed to parse",
            body=(
                "Claude's edit produced a plan file that no longer "
                "parses as valid YAML/frontmatter. Reverting "
                "strongly recommended."
            ),
            suggested_action=None,
        ),)
        return introduced, ()


@dataclass(frozen=True)
class EscalateResult:
    """Disposition of one :func:`escalate_to_split` call.

    ``outcome`` is exactly one of five strings:
      - ``"applied"`` — the split was written to ``plan_path``.
      - ``"recommended"`` — the bridge declined to mutate and emits a
        ``structural-split`` :class:`Recommendation` for the caller to
        surface (``allow_split=False``, a declined/non-TTY confirm, or a
        mid-apply graph error).
      - ``"unsafe"`` — a downstream non-``PENDING`` step blocks the split;
        ``blocking`` names the offending ids and no rec is emitted.
      - ``"proposal-unusable"`` — the proposer returned nothing parseable.
      - ``"step-missing"`` — ``step_id`` is not in the plan.

    ``recommendation`` is populated only on ``"recommended"``; ``blocking``
    only on ``"unsafe"``.
    """

    outcome: str
    target_id: int
    recommendation: Optional[Recommendation] = None
    blocking: list[int] = field(default_factory=list)


def _structural_split_rec(step: Step) -> Recommendation:
    """Build the advisory ``structural-split`` recommendation for ``step``.

    Non-apply-eligible by source (see ``review.STRUCTURAL_SOURCES`` /
    ``review.APPLY_ELIGIBLE_SOURCES``): the only correct fix for a mixed
    refactor+feature step is to split it into two type-pure steps, which
    ``apply_finding`` cannot do. The suggested action points at the real
    ``plan-tool split`` surface (``cmd_split`` in ``cli/authoring.py``).
    """
    title = (
        f"Step {step.id} ({step.title!r}) mixes refactor + feature — split it"
    )
    body = (
        f"Step {step.id} mixes behavior-preserving restructuring with new "
        "behavior. The only correct fix is to split it into two type-pure "
        "steps — the refactor first, then the feature — which an apply edit "
        "cannot do."
    )
    suggested = (
        f"plan-tool split <plan> --step {step.id} "
        '--into "<refactor half>" --into "<feature half>"'
    )
    return Recommendation(
        id=_make_rec_id(step.id, "structural-split", f"structural-split:{step.id}"),
        source="structural-split",
        severity="medium",
        step_id=step.id,
        title=title,
        body=body,
        suggested_action=suggested,
    )


@spawn_cwd_from_repo_root
def escalate_to_split(
    plan_path: Path,
    *,
    step_id: int,
    repo_root: Path,
    invoker: Callable[[str], str],
    allow_split: bool,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> EscalateResult:
    """Apply-or-recommend the refactor+feature split of one mixed step.

    The single reusable seam later wired into the ``create``/``detail``
    convergence loops and the ``review_actions`` ``BLOCKED-STRUCTURAL``
    branch. It mirrors :func:`plan_tool.detail.generate_detail`'s inline
    Phase-B sequence call-for-call — re-parse from disk → safe-gate →
    propose once → confirm → apply → migrate → write — re-deriving no
    algorithm, only routing through the five existing split primitives. It
    either **applies** the split or **recommends** it, never half-doing it.

    The deterministic safe-gate and the ``allow_split`` recommend-only
    check both run **before** any Claude proposal, so no token is spent on
    a path that can never apply.

    ``invoker`` is the split-proposer seam (``Callable[[str], str]``,
    returns raw text :func:`_propose_step_split` parses) — *not* the
    ``Invoker`` run-step alias; pass it explicitly so a test's no-Claude
    paths are provable. ``prompt_fn`` defaults to the interactive
    :func:`input`; a non-TTY caller still recommends rather than blocks
    because ``_confirm_split`` auto-declines off a TTY.

    The bridge does the structural edit only — both new halves are left
    ``detail is None`` for the caller's loop to re-author.
    """
    # Body-local: create.py / detail.py both import ``apply_finding`` from
    # this module at top level, so importing back from them must be lazy.
    from plan_tool.create import CreateError, _apply_step_split, _propose_step_split
    from plan_tool.detail import (
        _confirm_split,
        _migrate_and_write_split,
    )
    from plan_tool.split_safety import split_is_safe

    confirm_fn = prompt_fn if prompt_fn is not None else input

    plan = parse_plan(plan_path)

    # Best-effort decision telemetry: one `escalate-split` line per completed
    # call, carrying the final outcome. Snapshot the plan fingerprint + slug at
    # decision time (before an `applied` path's write_plan), so the event
    # captures the plan the bridge acted on. Both computes are guarded so a
    # fingerprint/slug failure can never perturb the bridge's outcome; the
    # recorder swallows its own errors. Escalate carries plan_fingerprint only
    # (a structure/safety decision, no code axis). See DATA_CONTRACT.md.
    try:
        from plan_tool.review_persistence import compute_plan_fingerprint

        escalate_plan_fp = compute_plan_fingerprint(plan_path)
    except Exception:
        escalate_plan_fp = ""
    try:
        escalate_slug = slug_from_filename(plan_path) or ""
    except Exception:
        escalate_slug = ""

    def _record_and_return(result: EscalateResult) -> EscalateResult:
        # Best-effort, symmetric with apply_finding's record_apply_verdict guard:
        # record_decision swallows its own errors, but wrap the recorder call
        # itself so a raising/monkeypatched recorder can never perturb the split
        # bridge's return (ground rule 2 — telemetry never changes control flow).
        try:
            record_escalate_split(
                repo_root,
                plan_slug=escalate_slug,
                outcome=result.outcome,
                allow_split=allow_split,
                step_id=step_id,
                blocking=result.blocking,
                plan_fingerprint=escalate_plan_fp,
            )
        except Exception:
            pass
        return result

    try:
        step = plan.step_by_id(step_id)
    except KeyError:
        return _record_and_return(
            EscalateResult(outcome="step-missing", target_id=step_id)
        )

    safe, blocking = split_is_safe(plan, step_id)
    if not safe:
        return _record_and_return(
            EscalateResult(outcome="unsafe", target_id=step_id, blocking=blocking)
        )

    if not allow_split:
        return _record_and_return(
            EscalateResult(
                outcome="recommended",
                target_id=step_id,
                recommendation=_structural_split_rec(step),
            )
        )

    replacements = _propose_step_split(step, invoker, repo_root=repo_root)
    if not replacements:
        return _record_and_return(
            EscalateResult(outcome="proposal-unusable", target_id=step_id)
        )

    if not _confirm_split(confirm_fn, step=step, replacements=replacements):
        return _record_and_return(
            EscalateResult(
                outcome="recommended",
                target_id=step_id,
                recommendation=_structural_split_rec(step),
            )
        )

    shift = len(replacements) - 1
    try:
        new_steps = _apply_step_split(plan.steps, step_id, replacements)
    except CreateError:
        return _record_and_return(
            EscalateResult(
                outcome="recommended",
                target_id=step_id,
                recommendation=_structural_split_rec(step),
            )
        )
    _migrate_and_write_split(
        plan_path,
        plan,
        new_steps,
        repo_root=repo_root,
        target_id=step_id,
        shift=shift,
    )
    # Best-effort step-provenance telemetry (#238 plan-mass "audit-induced
    # growth") — same signal `detail.split_step` records, for this bridge's
    # own applied mutation. See `record_escalate_split`'s guard above for why
    # this never perturbs the already-completed write. Fingerprint computed
    # *after* the write (unlike `escalate_plan_fp` above, deliberately
    # pre-mutation for `record_escalate_split`'s own "plan the bridge acted
    # on" framing) — matches `detail.split_step`'s post-mutation fingerprint,
    # so a step-provenance event always joins to the plan snapshot that
    # actually contains the new steps, regardless of which producer wrote it.
    try:
        from plan_tool.review_persistence import compute_plan_fingerprint

        record_step_provenance(
            repo_root,
            plan_slug=escalate_slug,
            new_step_titles=[r.title for r in replacements],
            mechanism="escalate-split",
            plan_fingerprint=compute_plan_fingerprint(plan_path),
        )
    except Exception:
        pass
    return _record_and_return(
        EscalateResult(outcome="applied", target_id=step_id)
    )


@spawn_cwd_from_repo_root
def apply_finding(
    plan_path: Path,
    *,
    repo_root: Path,
    finding_body: str,
    step_id: Optional[int],
    targeted_fix: Optional[str] = None,
    operator_feedback: Optional[str] = None,
    carried_findings: Sequence[CarriedFinding] = (),
    plan_name: Optional[str] = None,
    dry_run: bool = False,
    invoker: Invoker = shell_invoker,
    reporter: Optional[ProgressReporter] = None,
    auto_fix_introduced: bool = True,
    allow_structural_verdict: bool = False,
    run_logger: Optional["RunLogWriter"] = None,
    anchor: str = "",
    plan_fingerprint: str = "",
    risk_context_block: str = "",
    record_verdict: bool = True,
    verdict_observer: Optional[Callable[[DeferredApplyVerdict], None]] = None,
) -> ApplyFindingResult:
    """Invoke Claude to apply a single audit finding to the plan.

    The flow:

    1. Resolve the target step (``step_id`` if given; current/next runnable
       otherwise — same rules as :func:`run_step`).
    2. Snapshot the plan file plus the step's detail file so the caller
       can revert if the user rejects the diff.
    3. Render the ``apply-finding`` prompt (full plan content, step
       context, finding body, the audit's ``targeted_fix`` and any
       ``operator_feedback`` the walk collected — the latter is
       authoritative steering that refines the fix).
    4. Invoke Claude with ``acceptEdits`` — Claude edits the file(s)
       in-place via its Edit/Write tools.
    5. Compute a unified diff across the tracked files.
    6. Parse ``## Verdict`` (APPLIED / NOT-APPLICABLE / BLOCKED /
       BLOCKED-STRUCTURAL) and ``## Summary`` from the response. The
       ``BLOCKED-STRUCTURAL`` option is offered to Claude only when
       ``allow_structural_verdict`` is ``True`` (opt-in callers); the
       default keeps it absent so ``create``'s callers never emit it.
    7. Delete tracked detail files the apply created (declared-but-absent
       paths), then re-run the deterministic correctness/completeness
       primitives to compute ``introduced`` / ``resolved`` deltas against
       that cleaned tree.
    8. When ``auto_fix_introduced`` is ``True`` and the apply landed but
       introduced new findings (and the plan still parses), bundle the
       regressions into a single follow-up finding and invoke Claude
       once more to fix them in one shot. The diff and delta are then
       recomputed against the original pre-edit state, and any detail
       file the follow-up created is stripped the same way.

    With ``dry_run=True``, returns the rendered prompt without invoking
    Claude. Other fields are empty / sentinel.

    On non-zero exit code, the snapshot is automatically restored — a
    failed run shouldn't leave the plan in an in-between state. A raised
    invocation also attempts every tracked restore before propagating the
    original exception; ``exception.apply_finding_restore_succeeded`` exposes
    whether the state is safe for a deferred caller to continue. The caller
    (walk's apply branch) is responsible for asking the user whether to keep
    the diff on a successful run; this function returns the diff and the
    snapshot, but doesn't prompt.

    The follow-up call only fires once. If it fails or fails to clean up
    the regressions, the surviving findings are returned so the caller
    can surface them to the user.

    ``carried_findings`` is advisory prompt context only — the findings the
    iterate loop already surfaced this run — rendered into the prompt to
    steer the apply away from already-blocked remedies. It never widens the
    tracked/revert set ``apply_finding`` may edit.

    ``record_verdict=False`` suppresses durable decision rows while preserving
    classification. ``verdict_observer`` receives each launcher-classified
    outcome, including restoration safety before a raised invocation is
    propagated, so a deferred caller can persist only its accepted result.
    """
    plan = parse_plan(plan_path)
    step = resolve_step(plan, step_id)

    # Track plan + EVERY step's detail file for snapshot/diff. The
    # finding may target a step other than the one ``resolve_step``
    # picked: plan-wide review/completeness recs carry no ``step_id``,
    # so resolution falls to the current/next-runnable step, but Claude
    # edits the finding's real target — which can be any step's detail
    # file. Tracking only the resolved step's detail would both miss
    # that edit (empty diff → false "nothing changed" → rec recorded
    # un-applied) and leave it unreverted on decline/parse-failure
    # (the snapshot wouldn't cover it). Snapshotting all detail files
    # keeps the diff and the revert correct wherever the edit lands.
    # Pointer first, canonical second: a step whose ``detail:`` was never
    # persisted still has an on-disk body the reviewer is shown, so it must be
    # snapshotted too or an edit there is invisible to the diff and survives a
    # decline. Same resolution rule as the quality checks and the prompts.
    from plan_tool.detail_artifacts import resolve_detail_artifact

    tracked: list[Path] = [plan_path]
    seen_resolved: set[Path] = {plan_path.resolve()}
    for tracked_step in plan.steps:
        if tracked_step.detail:
            detail_abs = (repo_root / tracked_step.detail).resolve()
        else:
            resolution = resolve_detail_artifact(
                plan_path, plan, tracked_step, repo_root
            )
            if not resolution.on_disk:
                continue
            detail_abs = resolution.path.resolve()
        if detail_abs in seen_resolved:
            continue
        seen_resolved.add(detail_abs)
        tracked.append(detail_abs)

    # Refuse before the first snapshot, model call, or mutation: every
    # current on-disk detail file this apply might touch (or might revert
    # around) must declare a supported format version. Missing/non-file
    # paths (a set-but-missing pointer) keep their existing tracking
    # behavior — only a present, readable, unsupported body refuses.
    for detail_abs in tracked[1:]:
        if not detail_abs.is_file():
            continue
        try:
            detail_text = detail_abs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        require_supported_detail_format_version(detail_text, path=detail_abs)

    pre_snapshot = _snapshot_text_files(tracked)

    # Snapshot the pre-edit deterministic findings so we can compute
    # the introduced/resolved delta after the edit. Done lazily inside
    # the function so the import doesn't cause a load-time cycle
    # (review imports launcher transitively for FileExistence).
    from plan_tool.review import collect_deterministic_findings

    pre_findings = collect_deterministic_findings(
        plan, plan_path, repo_root=repo_root,
        plan_name=plan_name or plan_path.stem,
    )
    pre_finding_ids = {r.id for r in pre_findings}

    resolved_plan_slug = plan_name or slug_from_filename(plan_path.name) or ""

    def publish_verdict(
        verdict: str, *, restoration_succeeded: bool = True
    ) -> None:
        """Expose classification and optionally make the durable attempt."""
        observed = DeferredApplyVerdict(
            verdict=verdict,
            step_id=step.id,
            restoration_succeeded=restoration_succeeded,
        )
        if verdict_observer is not None:
            try:
                verdict_observer(observed)
            except Exception:
                pass
        if not record_verdict:
            return
        try:
            record_apply_verdict(
                repo_root,
                plan_slug=resolved_plan_slug,
                verdict=verdict,
                step_id=str(step.id),
                anchor=anchor,
                plan_fingerprint=plan_fingerprint,
            )
        except Exception:
            # The recorder is best-effort itself; retain this guard for test
            # doubles and out-of-tree monkeypatches that violate that contract.
            pass

    # Render via the standard renderer; supply the apply-finding-specific
    # extras (plan_content, plan_path, detail_path, finding_body).
    try:
        plan_rel = plan_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        plan_rel = str(plan_path)

    if step.detail is not None:
        detail_abs = (repo_root / step.detail).resolve()
        if detail_abs.is_file():
            detail_path_str = step.detail
        else:
            detail_path_str = (
                f"{step.detail} (not authored yet — no file at this path)"
            )
    else:
        detail_path_str = "(no detail file declared for this step)"

    # When the audit handed us a concrete targeted fix (plan-audit
    # findings carry one on ``suggested_action``), render it into the
    # prompt so claude applies exactly the edit the walk showed the user
    # rather than re-deriving one. Empty block for bundles / sources with
    # no fix — keeps the apply free to read the gap and decide.
    extra_vars = {
        "plan_path": plan_rel,
        "plan_content": pre_snapshot[plan_path] or "",
        "detail_path": detail_path_str,
        "finding_body": finding_body.strip(),
        "finding_fix_block": _format_targeted_fix_block(targeted_fix),
        "operator_feedback_block": _format_feedback_block(operator_feedback),
        "carried_findings_block": _format_carried_context_block(
            carried_findings
        ),
        "risk_context_block": risk_context_block,
        "structural_verdict_option": _STRUCTURAL_VERDICT_OPTION
        if allow_structural_verdict
        else "",
        "verdict_response_format_block": _apply_verdict_prompt_contract(
            allow_structural_verdict=allow_structural_verdict
        ).render_prompt_block(),
    }
    prompt = render_prompt(
        plan, step, repo_root=repo_root, mode="apply-finding",
        extra_vars=extra_vars,
    )

    if dry_run:
        return ApplyFindingResult(
            step_id=step.id, exit_code=0, verdict="UNKNOWN",
            summary="", diff_text="", pre_snapshot=pre_snapshot,
            stdout="", prompt=prompt,
        )

    if reporter is None:
        reporter = StderrReporter()
    # Label the progress line with the finding being applied, not the
    # step title — the title just repeats the step description on every
    # apply and tells the operator nothing about which finding is in
    # flight. For a single finding, ``finding_body``'s first line is
    # ``[SEVERITY] Title`` (see ``_format_findings_as_body``); for a
    # bundle it's the "address all N" directive. The progress module
    # caps and ellipsizes long labels.
    finding_label = next(
        (ln.strip() for ln in finding_body.splitlines() if ln.strip()),
        "finding",
    )
    handle = reporter.start_step(
        1, 1, f"apply-finding step {step.id}: {finding_label}"
    )
    # Caller (``_dispatch_apply_finding`` in cli.py) owns the
    # surrounding ``apply_finding_dispatch`` phase so the wrap covers
    # snapshot + diff + delta work too. We only emit the inner
    # claude_call_start / shell-sink events here.
    if run_logger is not None:
        run_logger.claude_call_start(
            phase="apply_finding_dispatch",
            attempt=1,
            prompt_bytes=_streaming_prompt_bytes(prompt),
            prompt_sha256=hash_prompt(prompt),
            step_id=step.id,
        )
        ctx = run_logger.bind_shell_sink(
            phase="apply_finding_dispatch", attempt=1,
        )
    else:
        ctx = nullcontext()
    start = time.monotonic()
    try:
        with ctx:
            exit_code, stdout = _invoke_and_log_end(
                invoker, prompt, run_logger=run_logger,
                started_monotonic=start, attempt=1,
            )
    except BaseException as invocation_error:
        restored_all = _restore_text_files_after_invocation_exception(pre_snapshot)
        _expose_invocation_restore_status(invocation_error, restored_all)
        publish_verdict(
            APPLY_VERDICT_INVOCATION_FAILED,
            restoration_succeeded=restored_all,
        )
        raise
    elapsed = time.monotonic() - start
    if exit_code != 0:
        handle.fail(elapsed, f"{get_active_backend().name} exited with code {exit_code}")
        # Restore so a failed run doesn't leave half-applied state.
        _restore_text_files(pre_snapshot)
        publish_verdict(APPLY_VERDICT_INVOCATION_FAILED)
        return ApplyFindingResult(
            step_id=step.id, exit_code=exit_code, verdict="UNKNOWN",
            summary="", diff_text="", pre_snapshot=pre_snapshot,
            stdout=stdout,
        )
    handle.complete(elapsed, len(stdout.encode("utf-8")))

    post_snapshot = _snapshot_text_files(tracked)
    diff_text = _render_diff(pre_snapshot, post_snapshot, repo_root=repo_root)
    verdict = parse_apply_verdict(stdout) or "UNKNOWN"
    # Best-effort decision telemetry: one line per real apply parse. Only
    # reachable applies (exit 0) record — the dry_run and non-zero-exit
    # returns leave before this line, so a recorded UNKNOWN means "apply ran
    # but Claude emitted no verdict token", never a backend crash (that lives
    # in the run-log). See DATA_CONTRACT.md. ``record_apply_verdict`` swallows
    # its own errors; the extra guard keeps a monkeypatched/raising recorder
    # from ever touching the apply's return.
    publish_verdict(verdict)
    # Prefer the stream-json ``result`` envelope (clean, tool-noise-free)
    # when the invoker carries one; otherwise scan the full stdout, since
    # acceptEdits edit-tool output can push the ``## Summary`` block past
    # the default 4 KB tail and silently blank the disposition note.
    invoker_stats = _invoker_stats(invoker)
    summary = extract_summary(
        stdout,
        final_text=invoker_stats.final_text,
        full_stdout_scan=True,
    ) or ""
    if verdict == "APPLIED" and not summary:
        # The edit landed but Claude emitted no parseable ``## Summary``,
        # so the disposition note would read a bare "applied finding:"
        # with no description of what changed. Surface it where users
        # look rather than swallowing it. (Raw stdout is captured in the
        # run log via the bound shell sink when a run_logger is active.)
        print(
            f"warning: apply-finding for step {step.id} reported APPLIED "
            "but produced no `## Summary` line; the disposition note will "
            "lack a description of the change",
            file=sys.stderr,
        )
        logger.info(
            "apply_finding step %s: APPLIED verdict with no extractable "
            "summary", step.id,
        )

    # Strip detail files the apply created before judging regressions or
    # firing auto-fix — otherwise an ephemeral created file can seed the
    # delta and burn a follow-up call on something this function will delete.
    removed_created: tuple[str, ...] = ()
    if verdict == "APPLIED":
        removed_created = _remove_unauthorized_created_files(pre_snapshot)
        if removed_created:
            post_snapshot = _snapshot_text_files(tracked)
            diff_text = _render_diff(
                pre_snapshot, post_snapshot, repo_root=repo_root
            )

    # Compute pre/post findings delta only when the edit succeeded
    # AND something actually changed on disk. For BLOCKED /
    # BLOCKED-STRUCTURAL / NOT-APPLICABLE / UNKNOWN, or clean APPLIED
    # with no diff, the plan state is unchanged so the delta is empty
    # by definition; skip the work.
    introduced: tuple = ()
    resolved: tuple = ()
    if verdict == "APPLIED" and diff_text:
        introduced, resolved = _compute_findings_delta(
            plan_path, pre_findings, pre_finding_ids,
            repo_root=repo_root, plan_name=plan_name, step_id=step.id,
        )

    # Auto-fix pass: if the apply landed cleanly but the validation
    # primitives flagged new regressions, ask Claude to fix all of them
    # in one follow-up call. We skip on parse-failure (plan is broken;
    # don't pile more edits onto a broken file) and when the caller
    # opts out (tests, scripted bulk runs).
    parse_failed = any(
        r.id == POST_EDIT_PARSE_FAILURE_ID for r in introduced
    )
    if (
        auto_fix_introduced
        and verdict == "APPLIED"
        and diff_text
        and introduced
        and not parse_failed
    ):
        followup_body = _format_findings_as_body(introduced)
        # Re-render with the post-first-edit plan content so Claude
        # sees the current state, not the pre-edit state.
        try:
            followup_plan = parse_plan(plan_path)
            followup_step = resolve_step(followup_plan, step.id)
        except Exception:
            followup_plan = plan
            followup_step = step
        followup_extra_vars = {
            "plan_path": plan_rel,
            "plan_content": plan_path.read_text(encoding="utf-8"),
            "detail_path": detail_path_str,
            "finding_body": followup_body,
            # Regression bundles describe their own edits; no single
            # targeted fix to inject and no carried advisory context.
            "finding_fix_block": "",
            "operator_feedback_block": _format_feedback_block(operator_feedback),
            "carried_findings_block": "",
            "risk_context_block": risk_context_block,
            "structural_verdict_option": _STRUCTURAL_VERDICT_OPTION
            if allow_structural_verdict
            else "",
            "verdict_response_format_block": _apply_verdict_prompt_contract(
                allow_structural_verdict=allow_structural_verdict
            ).render_prompt_block(),
        }
        followup_prompt = render_prompt(
            followup_plan, followup_step, repo_root=repo_root,
            mode="apply-finding", extra_vars=followup_extra_vars,
        )
        fhandle = reporter.start_step(
            1, 1,
            f"apply-finding follow-up step {step.id}: "
            f"fix {len(introduced)} regression(s)",
        )
        if run_logger is not None:
            run_logger.claude_call_start(
                phase="apply_finding_dispatch",
                attempt=2,
                prompt_bytes=_streaming_prompt_bytes(followup_prompt),
                prompt_sha256=hash_prompt(followup_prompt),
                step_id=step.id,
            )
            fctx = run_logger.bind_shell_sink(
                phase="apply_finding_dispatch", attempt=2,
            )
        else:
            fctx = nullcontext()
        # A raised follow-up must discard only that attempt's partial edits.
        # Keep the successful primary apply as the caller-visible candidate.
        followup_snapshot = _snapshot_text_files(tracked)
        fstart = time.monotonic()
        try:
            with fctx:
                fexit, fstdout = _invoke_and_log_end(
                    invoker, followup_prompt, run_logger=run_logger,
                    started_monotonic=fstart, attempt=2,
                )
        except BaseException as invocation_error:
            # Authoritative serial callers keep the successful primary edit so
            # the operator can decide its fate. Deferred callers (parallel
            # workers/conflict reruns and interactive review) have not accepted
            # any result yet, so a failed compound apply restores the original
            # invocation snapshot and cannot leak a partial candidate.
            failed_attempt_snapshot = (
                followup_snapshot if record_verdict else pre_snapshot
            )
            restored_all = _restore_text_files_after_invocation_exception(
                failed_attempt_snapshot
            )
            _expose_invocation_restore_status(invocation_error, restored_all)
            publish_verdict(
                APPLY_VERDICT_INVOCATION_FAILED,
                restoration_succeeded=restored_all,
            )
            raise
        felapsed = time.monotonic() - fstart
        if fexit == 0:
            fhandle.complete(felapsed, len(fstdout.encode("utf-8")))
            # Recompute diff and delta against the *original* pre-edit
            # state — the caller's revert target hasn't moved.
            post_snapshot = _snapshot_text_files(tracked)
            diff_text = _render_diff(
                pre_snapshot, post_snapshot, repo_root=repo_root
            )
            followup_stats = _invoker_stats(invoker)
            followup_summary = extract_summary(
                fstdout,
                final_text=followup_stats.final_text,
                full_stdout_scan=True,
            ) or ""
            if followup_summary:
                summary = (
                    f"{summary} (+ follow-up: {followup_summary})"
                    if summary else f"follow-up: {followup_summary}"
                )
            stdout = stdout + "\n\n--- follow-up ---\n" + fstdout
            if diff_text:
                introduced, resolved = _compute_findings_delta(
                    plan_path, pre_findings, pre_finding_ids,
                    repo_root=repo_root, plan_name=plan_name,
                    step_id=step.id,
                )
            else:
                # Follow-up reverted everything (back to pre-edit
                # state). Treat as APPLIED-no-op: empty delta.
                introduced, resolved = (), ()
            # Follow-up can create the same declared-but-absent path;
            # strip it and re-diff / re-delta against the cleaned tree.
            followup_removed = _remove_unauthorized_created_files(pre_snapshot)
            if followup_removed:
                removed_created = removed_created + followup_removed
                post_snapshot = _snapshot_text_files(tracked)
                diff_text = _render_diff(
                    pre_snapshot, post_snapshot, repo_root=repo_root
                )
                if diff_text:
                    introduced, resolved = _compute_findings_delta(
                        plan_path, pre_findings, pre_finding_ids,
                        repo_root=repo_root, plan_name=plan_name,
                        step_id=step.id,
                    )
                else:
                    introduced, resolved = (), ()
        else:
            fhandle.fail(felapsed, f"{get_active_backend().name} exited with code {fexit}")
            publish_verdict(APPLY_VERDICT_INVOCATION_FAILED)
            # Don't revert the first apply — the user-facing finding
            # was successfully applied. Surface the regressions so
            # the caller's confirmation prompt warns the user.

    return ApplyFindingResult(
        step_id=step.id, exit_code=0, verdict=verdict,
        summary=summary, diff_text=diff_text,
        pre_snapshot=pre_snapshot, stdout=stdout,
        introduced_findings=introduced,
        resolved_findings=resolved,
        removed_created_detail_files=removed_created,
    )


@dataclass(frozen=True)
class BulletResult:
    """One acceptance-bullet result from ``verify --deep``.

    ``verdict`` is ``"PASS"`` / ``"FAIL"`` / ``"UNKNOWN"``. Caller maps
    contract misses (claude returned no parseable verdict) to
    ``"UNKNOWN"`` so the rollup math doesn't have to special-case
    ``None``.
    """

    bullet: str
    verdict: str


@dataclass(frozen=True)
class VerifyVerdict:
    """Aggregated reconcile result for a single done step.

    ``passed`` is True when the step had a parseable findings block with
    zero ``CRITICAL`` items and the underlying claude call exited 0.
    ``status`` is the human-facing label rendered on the verdict line.

    ``bullet_results`` is populated only by ``verify --deep``; the
    standard verify path leaves it as the empty default. Each entry
    carries the bullet text and the per-bullet PASS/FAIL/UNKNOWN
    verdict.
    """

    step_id: int
    step_title: str
    passed: bool
    status: str  # "pass" | "warn" | "fail"
    findings: FindingsSummary
    exit_code: int
    verdict_line: str
    bullet_results: tuple[BulletResult, ...] = ()


def verify_plan(
    plan_path: Path,
    *,
    repo_root: Path,
    invoker: Invoker = shell_invoker,
    max_steps: Optional[int] = None,
    dry_run: bool = False,
    reporter: Optional[ProgressReporter] = None,
    deep: bool = False,
) -> list[VerifyVerdict]:
    """Run the detail-reconcile prompt across every done step and aggregate verdicts.

    Thin wrapper over :func:`run_all_done_steps` (mode=``detail-reconcile``)
    plus :func:`summarize_findings`. Returns one :class:`VerifyVerdict` per
    done step with the per-step pass/warn/fail status the CLI prints.

    Empty done-step case: returns an empty list. The CLI distinguishes
    "nothing to verify" from "every done step passed" so a fresh plan
    doesn't look like a successful audit.

    When ``deep=True`` and the reconcile pass exited 0, each step's
    detail-file acceptance bullets are checked individually via
    ``prompts/reconcile-deep.md`` and the rollup overrides the
    reconcile verdict:

      - any bullet ``FAIL`` → step ``fail`` (passed=False)
      - all ``PASS`` → step ``pass``
      - mixed ``PASS`` + ``UNKNOWN`` → step ``warn`` (passed=True)
      - no parseable bullets → fall back to the reconcile verdict
        (no override)
    """
    results = run_all_done_steps(
        plan_path,
        repo_root=repo_root,
        mode="detail-reconcile",
        invoker=invoker,
        max_steps=max_steps,
        dry_run=dry_run,
        reporter=reporter,
    )
    verdicts: list[VerifyVerdict] = []
    for r in results:
        if r.exit_code != 0:
            findings = FindingsSummary(parsed=False, counts={}, unspecified=0)
            status = "fail"
            line = (
                f"Step {r.step_id} — {get_active_backend().name} exited "
                f"with code {r.exit_code}"
            )
            verdicts.append(
                VerifyVerdict(
                    step_id=r.step_id,
                    step_title=r.step_title,
                    passed=False,
                    status=status,
                    findings=findings,
                    exit_code=r.exit_code,
                    verdict_line=line,
                )
            )
            continue
        findings = summarize_findings(r.stdout)
        line = format_findings_verdict(r.step_id, findings)
        if not findings.parsed:
            status = "warn"
            passed = True  # contract miss doesn't count as a fail
        elif findings.critical > 0:
            status = "fail"
            passed = False
        elif (findings.counts.get("HIGH", 0) > 0
              or findings.counts.get("MEDIUM", 0) > 0
              or findings.unspecified > 0):
            status = "warn"
            passed = True
        else:
            status = "pass"
            passed = True

        bullet_results: tuple[BulletResult, ...] = ()
        if deep and not dry_run:
            deep_outcome = _run_deep_for_step(
                plan_path,
                step_id=r.step_id,
                repo_root=repo_root,
                invoker=invoker,
                reporter=reporter,
            )
            if deep_outcome is not None:
                bullet_results, status, passed, line = deep_outcome

        verdicts.append(
            VerifyVerdict(
                step_id=r.step_id,
                step_title=r.step_title,
                passed=passed,
                status=status,
                findings=findings,
                exit_code=r.exit_code,
                verdict_line=line,
                bullet_results=bullet_results,
            )
        )
    return verdicts


def _run_deep_for_step(
    plan_path: Path,
    *,
    step_id: int,
    repo_root: Path,
    invoker: Invoker,
    reporter: Optional[ProgressReporter],
) -> Optional[tuple[tuple[BulletResult, ...], str, bool, str]]:
    """Run the deep-reconcile pass for one done step.

    Returns ``(bullet_results, status, passed, verdict_line)`` when the
    step had parseable acceptance bullets, or ``None`` when the deep
    pass should be skipped (no detail file, no acceptance section, no
    bullets) — caller falls back to the reconcile-derived verdict.

    Mutates nothing; reads the plan, the step's detail file, and
    invokes claude N times (one per bullet).
    """
    from plan_tool.detail import parse_acceptance_bullets

    plan = parse_plan(plan_path)
    try:
        step = plan.step_by_id(step_id)
    except KeyError:
        return None
    if step.detail is None:
        return None
    detail_path = repo_root / step.detail
    if not detail_path.is_file():
        return None
    try:
        body = detail_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        require_supported_detail_format_version(body, path=detail_path)
    except DetailFormatError as exc:
        raise LauncherError(
            f"step {step_id}: {exc}"
        ) from exc
    bullets = parse_acceptance_bullets(body)
    if not bullets:
        return None

    if reporter is None:
        reporter = StderrReporter()

    results: list[BulletResult] = []
    total = len(bullets)
    for idx, bullet in enumerate(bullets, start=1):
        prompt = render_prompt(
            plan,
            step,
            repo_root=repo_root,
            mode="reconcile-deep",
            extra_vars={
                "acceptance_bullet": bullet,
                "verdict_response_format_block": (
                    DEEP_VERDICT_RESPONSE_CONTRACT.render_prompt_block()
                ),
            },
        )
        handle = reporter.start_step(
            idx,
            total,
            f"step {step_id} bullet {idx}/{total}: {bullet[:60]}",
        )
        start = time.monotonic()
        exit_code, stdout = invoker(prompt)
        elapsed = time.monotonic() - start
        if exit_code != 0:
            handle.fail(elapsed, f"{get_active_backend().name} exited with code {exit_code}")
            results.append(BulletResult(bullet=bullet, verdict="UNKNOWN"))
            continue
        handle.complete(elapsed, len(stdout.encode("utf-8")))
        verdict = parse_deep_verdict(stdout)
        results.append(
            BulletResult(bullet=bullet, verdict=verdict or "UNKNOWN")
        )

    bullet_results = tuple(results)
    fail_count = sum(1 for r in results if r.verdict == "FAIL")
    unknown_count = sum(1 for r in results if r.verdict == "UNKNOWN")
    pass_count = sum(1 for r in results if r.verdict == "PASS")

    if fail_count > 0:
        status = "fail"
        passed = False
    elif unknown_count > 0:
        status = "warn"
        passed = True
    else:
        status = "pass"
        passed = True
    verdict_line = (
        f"Step {step_id} (deep) — {pass_count} pass / "
        f"{fail_count} fail / {unknown_count} unknown"
    )
    return bullet_results, status, passed, verdict_line


def run_all_done_steps(
    plan_path: Path,
    *,
    repo_root: Path,
    mode: str,
    invoker: Invoker = shell_invoker,
    max_steps: Optional[int] = None,
    dry_run: bool = False,
    reporter: Optional[ProgressReporter] = None,
) -> list[RunResult]:
    """Run a review mode against every done step in the plan, one subprocess each.

    Raises LauncherError if `mode` is a mutating mode or a selected detail
    cannot be rendered — use `run_step` for a mutating mode.
    Never modifies the plan file. `max_steps` limits invocations to the last N
    done steps by plan order.

    Progress: one ``[N/M] step X: <title> (mode=<mode>)`` line per claude
    call on stderr, with heartbeats during long calls and a closing
    ``done in Xs`` / ``FAILED in Xs`` per step. Dry-run emits no progress.
    """
    if mode in MUTATING_MODES:
        raise LauncherError(
            f"verify-all does not support mutating mode '{mode}'; "
            "use 'plan-tool run' to execute steps"
        )

    plan = parse_plan(plan_path)
    done_steps = [s for s in plan.steps if s.status == StepStatus.DONE]

    if max_steps is not None:
        done_steps = done_steps[-max_steps:]

    if not dry_run and reporter is None:
        reporter = StderrReporter()

    total = len(done_steps)
    results: list[RunResult] = []
    for idx, step in enumerate(done_steps, start=1):
        try:
            prompt = render_prompt(plan, step, repo_root=repo_root, mode=mode)
        except DetailGradeError as exc:
            raise LauncherError(str(exc)) from exc
        if dry_run:
            exit_code, stdout = 0, prompt
        else:
            assert reporter is not None  # narrowed by branch above
            handle = reporter.start_step(
                idx, total, f"step {step.id}: {step.title} (mode={mode})"
            )
            start = time.monotonic()
            exit_code, stdout = invoker(prompt)
            elapsed = time.monotonic() - start
            if exit_code == 0:
                handle.complete(elapsed, len(stdout.encode("utf-8")))
            else:
                handle.fail(elapsed, f"{get_active_backend().name} exited with code {exit_code}")
        results.append(RunResult(
            step_id=step.id,
            exit_code=exit_code,
            advanced_to=None,
            done=False,
            stdout=stdout,
            step_title=step.title,
        ))
    return results
