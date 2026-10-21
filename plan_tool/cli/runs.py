"""Run-log command module — the ``runs`` inspect / profile / manage verb.

Holds the ``runs`` handler (``cmd_runs``), its ``profile`` sub-action
(``_cmd_runs_profile``), the ``_CallSample`` dataclass and the
sampling/grouping/summarizing chain it aggregates over, the JSONL event
readers (``_iter_events`` / ``_load_events_with_skips``), the run-log
summarizers (``_summarize_run_log`` / ``_aggregate_run_for_diff``), and
the arg/target parsers + eviction predicate. A :func:`register`
contributes the ``runs`` subparser (with its list / show / diff /
profile / clear sub-actions) to the shared ``add_subparsers`` action
(see :mod:`plan_tool.cli.parser`).

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`) and
the domain packages — never :mod:`plan_tool.cli.app`. ``app`` re-imports
these names back into its own namespace so the package surface stays
intact — in particular ``_iter_events``, which the package-surface test
and ``tests/cli/test_state_cmds.py`` both import as
``from plan_tool.cli import _iter_events``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from plan_tool.cli.checkpoints import _safe_under_root, _validate_checkpoint_arg
from plan_tool.cli.console import _fmt_ms, _fmt_ms_or_n
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.run_log import (
    prune_stream_logs,
    IN_FLIGHT_FILENAME,
    RUN_LOG_SCHEMA_VERSION,
    run_dir,
    run_log_path,
    runs_root,
)
from plan_tool.style import error, note, warn

# Recommended default TTL for ``plan-tool runs clear --older-than``: a
# run log untouched for 30 days is overwhelmingly stale. Matches the
# ``DEFAULT_MAX_AGE_SECONDS`` cliff in ``checkpoint.py`` so users learn
# one cadence for both caches. Referenced by the ``--older-than`` help
# text and by step 8's docs / any future auto-eviction caller — change
# in one place if the cadence ever shifts.
_DEFAULT_RUNS_TTL_SECONDS = 30 * 24 * 60 * 60


def _iter_events(path: Path) -> Iterator[dict[str, Any]]:
    """Yield event dicts from a run-log JSONL, tolerating a partial last line.

    Skips any line that ``json.loads`` rejects or whose top-level value
    isn't a dict — matches the read-side contract that step 7 pins.
    Does not validate the ``event`` discriminator or required fields;
    callers that need typed events should layer on top.

    Callers that need to *report* the skipped-line count (e.g.
    ``runs show``, which exits 1 when every line is unparseable
    rather than rendering empty metadata) should use
    :func:`_load_events_with_skips` instead.
    """
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _load_events_with_skips(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Load every event from ``path`` and return ``(events, skipped)``.

    ``skipped`` counts non-blank lines that either failed
    ``json.loads`` or decoded to a non-dict top-level value. Blank
    lines are not counted as skips — they're whitespace, not damage.

    Used by ``runs show`` to surface ``"<N unreadable line(s)>"`` and
    exit 1 when every non-blank line was skipped (vs. a clean empty
    file, which exits 0). ``_iter_events`` stays the right call for
    consumers that only want the parseable events and can tolerate
    silent skips (``diff``, ``list`` row aggregation).
    """
    events: list[dict[str, Any]] = []
    skipped = 0
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(obj, dict):
                events.append(obj)
            else:
                skipped += 1
    return events, skipped


def _parse_duration_arg(value: str) -> Optional[int]:
    """Parse ``30d`` / ``48h`` / ``90m`` / ``3600`` to seconds.

    Returns ``None`` on garbage so ``cmd_runs`` can print a specific
    error and exit 2 — matches the ``_validate_checkpoint_arg``
    convention of returning Optional[error] rather than raising.
    """
    if not value:
        return None
    suffix_to_seconds = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    if value[-1] in suffix_to_seconds:
        try:
            n = int(value[:-1])
        except ValueError:
            return None
        if n < 0:
            return None
        return n * suffix_to_seconds[value[-1]]
    try:
        n = int(value)
    except ValueError:
        return None
    return n if n >= 0 else None


def _summarize_run_log(path: Path) -> dict[str, Any]:
    """Walk one JSONL once and pull headline fields for ``runs list``.

    Returns a dict with: ``command``, ``plan_slug``, ``started_at``,
    ``duration`` (``"in-flight"`` literal when no ``run_end``),
    ``event_count``, ``tokens_total`` (int when any
    ``claude_call_end`` carries non-None tokens, else ``None``),
    ``unreadable`` (True if the file could not be opened at all).
    Defaults to ``"?"`` for any field that the file did not carry.
    """
    summary: dict[str, Any] = {
        "command": "?",
        "plan_slug": "?",
        "started_at": "?",
        "duration": "?",
        "event_count": 0,
        "tokens_total": None,
        "unreadable": False,
    }
    saw_run_end = False
    tokens_seen = False
    tokens_total = 0
    try:
        for ev in _iter_events(path):
            summary["event_count"] += 1
            kind = ev.get("event")
            if kind == "run_start":
                summary["command"] = ev.get("command", "?") or "?"
                summary["plan_slug"] = ev.get("plan_slug", "?") or "?"
                ts = ev.get("ts", "?")
                summary["started_at"] = ts if isinstance(ts, str) else "?"
            elif kind == "run_end":
                saw_run_end = True
                dur = ev.get("duration_ms")
                if isinstance(dur, (int, float)):
                    summary["duration"] = f"{int(dur)}ms"
            elif kind == "claude_call_end":
                ti = ev.get("tokens_input")
                to = ev.get("tokens_output")
                if isinstance(ti, int):
                    tokens_total += ti
                    tokens_seen = True
                if isinstance(to, int):
                    tokens_total += to
                    tokens_seen = True
    except OSError:
        summary["unreadable"] = True
        return summary
    if not saw_run_end:
        summary["duration"] = "in-flight"
    if tokens_seen:
        summary["tokens_total"] = tokens_total
    return summary


def _aggregate_run_for_diff(path: Path) -> dict[str, dict[str, Any]]:
    """Build a per-phase aggregation for ``runs diff``.

    Returns a dict keyed by phase name with ``wall_ms`` (int),
    ``claude_call_count`` (int), ``tokens_in`` (int), ``tokens_out``
    (int), and ``tokens_seen`` (bool — False when every
    ``claude_call_end`` in that phase carried None for both token
    counts; the renderer uses this to print ``-`` rather than ``0``).
    A ``phase_start`` without a matching ``phase_end`` (in-flight or
    crashed run) contributes ``wall_ms=0`` for the phase. A
    ``phase_end`` without a matching ``phase_start`` is skipped.
    Also returns the file's ``schema_version`` under the special
    ``"__schema__"`` key (int or None when missing).
    """
    open_phases: list[str] = []
    aggregates: dict[str, dict[str, Any]] = {}
    schema: Optional[int] = None
    first_run_start_seen = False
    for ev in _iter_events(path):
        kind = ev.get("event")
        if kind == "run_start" and not first_run_start_seen:
            first_run_start_seen = True
            sv = ev.get("schema_version")
            if isinstance(sv, int):
                schema = sv
        if kind == "phase_start":
            phase = ev.get("phase")
            if isinstance(phase, str) and phase:
                open_phases.append(phase)
                aggregates.setdefault(
                    phase,
                    {
                        "wall_ms": 0,
                        "claude_call_count": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "tokens_seen": False,
                    },
                )
        elif kind == "phase_end":
            phase = ev.get("phase")
            if not (isinstance(phase, str) and phase):
                continue
            # Drop the most recent matching open phase (handles nested
            # phases like reconcile_walk → apply_finding_dispatch).
            if phase in open_phases:
                # Pop the most recent matching entry by walking from the
                # right; preserves outer phases when an inner one ends.
                for i in range(len(open_phases) - 1, -1, -1):
                    if open_phases[i] == phase:
                        open_phases.pop(i)
                        break
            else:
                continue
            agg = aggregates.setdefault(
                phase,
                {
                    "wall_ms": 0,
                    "claude_call_count": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_seen": False,
                },
            )
            dur = ev.get("duration_ms")
            if isinstance(dur, (int, float)):
                agg["wall_ms"] += int(dur)
        elif kind == "claude_call_start":
            phase = ev.get("phase")
            if isinstance(phase, str) and phase:
                agg = aggregates.setdefault(
                    phase,
                    {
                        "wall_ms": 0,
                        "claude_call_count": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "tokens_seen": False,
                    },
                )
                agg["claude_call_count"] += 1
        elif kind == "claude_call_end":
            phase = ev.get("phase")
            if not (isinstance(phase, str) and phase):
                continue
            agg = aggregates.setdefault(
                phase,
                {
                    "wall_ms": 0,
                    "claude_call_count": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_seen": False,
                },
            )
            ti = ev.get("tokens_input")
            to = ev.get("tokens_output")
            if isinstance(ti, int):
                agg["tokens_in"] += ti
                agg["tokens_seen"] = True
            if isinstance(to, int):
                agg["tokens_out"] += to
                agg["tokens_seen"] = True
    aggregates["__schema__"] = {"schema_version": schema}  # type: ignore[assignment]
    return aggregates


def _parse_runs_target(target: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Split ``<slug>/<run_id>[.jsonl]`` into ``(slug, run_id, error)``.

    Returns ``(slug, run_id, None)`` on success and
    ``(None, None, error_message)`` on a missing slash. Validation of
    the individual components is the caller's responsibility (it
    routes through ``_validate_checkpoint_arg``).
    """
    if "/" not in target:
        return None, None, (
            "target requires <slug>/<run_id> (e.g. "
            "my-plan/2026-05-14T12-34-56-9f3a1c)"
        )
    slug, run_id = target.split("/", 1)
    if run_id.endswith(".jsonl"):
        run_id = run_id[: -len(".jsonl")]
    return slug, run_id, None


def _is_run_evictable(
    jsonl_path: Path, cutoff_seconds: Optional[int]
) -> bool:
    """True when ``jsonl_path`` should be unlinked under the TTL.

    A path with no readable ``run_start`` event is treated as
    evictable only when ``cutoff_seconds`` is None (full wipe) —
    never under a TTL, because we can't determine its age. Symlinks
    are filtered by the caller before this is reached.
    """
    if cutoff_seconds is None:
        return True
    try:
        first = next(_iter_events(jsonl_path), None)
    except OSError:
        return False
    if not isinstance(first, dict) or first.get("event") != "run_start":
        return False
    ts = first.get("ts")
    if not isinstance(ts, str):
        return False
    try:
        started = datetime.fromisoformat(ts)
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - started).total_seconds()
    return age > cutoff_seconds


@dataclass(frozen=True)
class _CallSample:
    """One ``(claude_call_start, claude_call_end)`` pair extracted from a
    run log, plus the bits ``runs profile`` aggregates over.

    A start without a matching end carries ``incomplete=True`` and
    leaves the duration / rc / usage fields as ``None`` — the renderer
    counts the row but excludes it from the latency percentiles by
    default.
    """

    plan_slug: str
    run_id: str
    run_started_at: str
    step_id: Optional[int]
    attempt: int
    phase: str
    mode: Optional[str]
    duration_ms: Optional[int]
    rc: Optional[int]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    cache_creation_tokens: Optional[int]
    cache_read_tokens: Optional[int]
    cost_usd: Optional[float]
    incomplete: bool


def _iter_call_samples(
    jsonl_path: Path, *, plan_slug: str,
) -> list[_CallSample]:
    """Walk ``jsonl_path`` once and return one :class:`_CallSample` per
    paired ``claude_call_start`` event.

    Pairs a start with the next ``claude_call_end`` sharing the same
    ``(phase, attempt)`` — the launcher only records ``step_id`` on the
    start, so the start carries the step / mode forward into the
    sample. Mode is read from the most recent ``phase_start`` whose
    ``phase`` matches the start's ``phase`` (older logs without a mode
    field surface as ``None`` → bucketed under ``"?"``).

    Unmatched starts (subprocess crashed before its end was written)
    are appended at the tail with ``incomplete=True``. ``runs profile``
    decides whether to surface them in the count column via
    ``--include-incomplete``; the latency stats always skip them.
    """
    samples: list[_CallSample] = []
    run_id = ""
    run_started_at = ""
    # Map ``(phase, attempt)`` → LIFO stack of open starts. A given
    # ``run_step`` only has attempt=1 today, but the iterative
    # ``cmd_detail`` retry loop produces attempt=2/3 — preserve the
    # one-end-per-start invariant by popping the latest matching start.
    open_starts: dict[tuple[str, int], list[dict[str, Any]]] = {}
    # Last seen ``mode`` on a ``phase_start`` keyed by phase name —
    # claude_call_start doesn't carry mode itself.
    last_phase_mode: dict[str, Optional[str]] = {}

    try:
        for ev in _iter_events(jsonl_path):
            kind = ev.get("event")
            if kind == "run_start":
                rid = ev.get("run_id")
                run_id = rid if isinstance(rid, str) else ""
                ts = ev.get("ts")
                run_started_at = ts if isinstance(ts, str) else ""
            elif kind == "phase_start":
                phase = ev.get("phase")
                if isinstance(phase, str) and phase:
                    mode = ev.get("mode")
                    last_phase_mode[phase] = (
                        mode if isinstance(mode, str) else None
                    )
            elif kind == "claude_call_start":
                phase = ev.get("phase")
                if not isinstance(phase, str) or not phase:
                    continue
                attempt = ev.get("attempt")
                if not isinstance(attempt, int):
                    attempt = 1
                step_id = ev.get("step_id")
                start_record = {
                    "phase": phase,
                    "attempt": attempt,
                    "step_id": step_id if isinstance(step_id, int) else None,
                    "mode": last_phase_mode.get(phase),
                }
                open_starts.setdefault((phase, attempt), []).append(
                    start_record
                )
            elif kind == "claude_call_end":
                phase = ev.get("phase")
                if not isinstance(phase, str) or not phase:
                    continue
                attempt = ev.get("attempt")
                if not isinstance(attempt, int):
                    attempt = 1
                bucket = open_starts.get((phase, attempt))
                if not bucket:
                    # Orphan end (no matching start in this file).
                    # Skip — it can't be attributed to a step.
                    continue
                start_record = bucket.pop()
                dur = ev.get("duration_ms")
                rc = ev.get("rc")
                ti = ev.get("tokens_input")
                to = ev.get("tokens_output")
                cct = ev.get("cache_creation_tokens")
                crt = ev.get("cache_read_tokens")
                cost = ev.get("cost_usd")
                samples.append(
                    _CallSample(
                        plan_slug=plan_slug,
                        run_id=run_id,
                        run_started_at=run_started_at,
                        step_id=start_record["step_id"],
                        attempt=attempt,
                        phase=phase,
                        mode=start_record["mode"],
                        duration_ms=(
                            int(dur)
                            if isinstance(dur, (int, float))
                            else None
                        ),
                        rc=rc if isinstance(rc, int) else None,
                        tokens_input=ti if isinstance(ti, int) else None,
                        tokens_output=to if isinstance(to, int) else None,
                        cache_creation_tokens=(
                            cct if isinstance(cct, int) else None
                        ),
                        cache_read_tokens=(
                            crt if isinstance(crt, int) else None
                        ),
                        cost_usd=(
                            float(cost)
                            if isinstance(cost, (int, float))
                            else None
                        ),
                        incomplete=False,
                    )
                )
    except OSError:
        return samples

    for (phase, attempt), bucket in open_starts.items():
        for start_record in bucket:
            samples.append(
                _CallSample(
                    plan_slug=plan_slug,
                    run_id=run_id,
                    run_started_at=run_started_at,
                    step_id=start_record["step_id"],
                    attempt=start_record["attempt"],
                    phase=start_record["phase"],
                    mode=start_record["mode"],
                    duration_ms=None,
                    rc=None,
                    tokens_input=None,
                    tokens_output=None,
                    cache_creation_tokens=None,
                    cache_read_tokens=None,
                    cost_usd=None,
                    incomplete=True,
                )
            )
    return samples


def _group_samples(
    samples: list[_CallSample], by: str,
) -> dict[str, list[_CallSample]]:
    """Bucket samples by ``mode`` / ``step`` / ``run``.

    Falls back to a ``"?"`` key when the chosen field is None (older
    logs that did not record ``mode``, or starts that were missing a
    ``step_id`` field). Step keys are prefixed with the plan slug so
    two plans don't collide on the same integer id; run keys are
    ``<slug>/<run_id>``.
    """
    groups: dict[str, list[_CallSample]] = {}
    for s in samples:
        if by == "mode":
            key = s.mode or "?"
        elif by == "step":
            sid = "?" if s.step_id is None else str(s.step_id)
            key = f"{s.plan_slug}#{sid}"
        elif by == "run":
            key = (
                f"{s.plan_slug}/{s.run_id}"
                if s.run_id
                else s.plan_slug
            )
        else:
            key = "?"
        groups.setdefault(key, []).append(s)
    return groups


# BUG_BACKLOG: ``runs profile`` used to render p50 / p95 on buckets
# with fewer than 5 completed samples — numerically the output of
# ``statistics.quantiles`` interpolation, but statistically meaningless
# and read as authoritative. Below the threshold both quantiles stay
# ``None`` and the renderer prints ``n=<count>`` instead.
_SMALL_BUCKET_THRESHOLD = 5


def _summarize_group(
    samples: list[_CallSample], *, include_incomplete: bool,
) -> dict[str, Any]:
    """Aggregate one bucket into the columns ``runs profile`` prints.

    p50 / p95 come from ``statistics.quantiles(durations, n=20,
    method="inclusive")`` — index 9 is the median, index 18 is the
    95th percentile. Both stay ``None`` when fewer than
    ``_SMALL_BUCKET_THRESHOLD`` completed samples are available
    (small-sample interpolation produces "p95" numbers that read as
    authoritative but mean nothing); there is no single-sample
    fallback. ``min_ms`` / ``max_ms`` are computed from the same
    ``durations`` list as ``mean_ms`` / ``total_ms`` and so remain
    visible for every bucket size — they're what surfaces a slow
    outlier when the quantiles are suppressed. Token / cost columns
    sum only the samples that carried a value, so an older log that
    never populated ``tokens_input`` returns ``None`` (rendered as
    ``-``) instead of ``0`` (would look like "free").

    ``include_incomplete`` is forwarded to the count column policy:
    when False, incomplete samples are still counted in ``count`` (so
    the operator sees the call happened) but the ``incomplete`` column
    surfaces the orphaned count separately. When True, no behavioral
    change today — the flag is reserved for a future "drop incomplete
    rows entirely" toggle and the upstream filter is the same.
    """
    count = len(samples)
    incomplete = sum(1 for s in samples if s.incomplete)
    failed = sum(
        1 for s in samples
        if (not s.incomplete) and s.rc is not None and s.rc != 0
    )
    durations = [
        int(s.duration_ms)
        for s in samples
        if (not s.incomplete) and s.duration_ms is not None
    ]
    p50: Optional[float] = None
    p95: Optional[float] = None
    mean: Optional[float] = None
    total: Optional[int] = None
    min_ms: Optional[int] = None
    max_ms: Optional[int] = None
    if durations:
        total = sum(durations)
        mean = total / len(durations)
        min_ms = min(durations)
        max_ms = max(durations)
        if len(durations) >= _SMALL_BUCKET_THRESHOLD:
            cuts = statistics.quantiles(
                durations, n=20, method="inclusive",
            )
            # n=20 → 19 cut points indexed 0..18. q[9] is the median
            # (10th of 20 buckets), q[18] is the 95th percentile.
            p50 = cuts[9]
            p95 = cuts[18]

    cost_samples = [s.cost_usd for s in samples if s.cost_usd is not None]
    tin_samples = [s.tokens_input for s in samples if s.tokens_input is not None]
    tout_samples = [s.tokens_output for s in samples if s.tokens_output is not None]
    cache_read_samples = [
        s.cache_read_tokens for s in samples
        if s.cache_read_tokens is not None
    ]

    # When the caller explicitly opts out of incomplete rows, the
    # column would mislead: drop the count to zero so a JSON consumer
    # can rely on it being the surfaced number, not the underlying.
    if not include_incomplete:
        # No-op today: the count column still surfaces them. Documented
        # for the future-flag note above.
        pass

    return {
        "count": count,
        "fail": failed,
        "incomplete": incomplete,
        "p50_ms": p50,
        "p95_ms": p95,
        "mean_ms": mean,
        "total_ms": total,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "cost_usd": sum(cost_samples) if cost_samples else None,
        "tokens_input": sum(tin_samples) if tin_samples else None,
        "tokens_output": sum(tout_samples) if tout_samples else None,
        "cache_reads": (
            sum(cache_read_samples) if cache_read_samples else None
        ),
    }


def _cmd_runs_profile(
    args: argparse.Namespace, *, repo_root: Path, root: Path,
) -> int:
    """Render a per-mode / per-step / per-run latency + cost report.

    Walks ``<repo>/.plan-tool/runs/<slug>/*.jsonl``, skips in-flight
    runs (no ``run_end`` event), pairs each ``claude_call_start`` with
    its matching ``claude_call_end``, and aggregates the samples into
    the chosen ``--by`` bucket. Default ordering is by total
    wall-clock descending so the most expensive bucket sorts first.

    Exits:

    - ``0`` on success (including the no-data case, which prints
      ``"no runs"`` / ``"no claude calls"`` to stdout).
    - ``2`` on bad ``--slug`` / ``--since`` arguments.

    Buckets with fewer than ``_SMALL_BUCKET_THRESHOLD`` completed
    samples render the p50 / p95 cells as ``n=<N>`` (where N is
    ``count - incomplete``) instead of ms values — the underlying
    ``min`` / ``max`` columns remain visible so outliers are still
    surfaced. JSON consumers see ``p50_ms`` / ``p95_ms`` as ``null``
    in the suppressed case and can derive N from ``count`` -
    ``incomplete`` themselves.
    """
    if not root.is_dir():
        if args.json:
            print(
                json.dumps(
                    {"by": args.by, "groups": [], "runs_scanned": 0,
                     "runs_in_flight_skipped": 0},
                    separators=(",", ":"),
                )
            )
        else:
            print(f"no runs (root {root} does not exist)")
        return 0

    slug_filter: Optional[str] = args.slug
    if slug_filter is not None:
        err = _validate_checkpoint_arg(slug_filter, kind="slug")
        if err is not None:
            error(f"{err}")
            return 2

    since_seconds: Optional[int] = None
    if args.since is not None:
        since_seconds = _parse_duration_arg(args.since)
        if since_seconds is None:
            error(
                "--since expects e.g. 30d, 48h, 90m, or a positive "
                "integer (seconds)"
            )
            return 2
    cutoff_dt: Optional[datetime] = None
    if since_seconds is not None:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(
            seconds=since_seconds
        )

    if slug_filter is not None:
        slug_dirs = [run_dir(repo_root, slug_filter)]
    else:
        slug_dirs = sorted(
            p for p in root.iterdir()
            if p.is_dir() and not p.is_symlink()
        )

    all_samples: list[_CallSample] = []
    runs_scanned = 0
    runs_in_flight = 0
    for slug_dir in slug_dirs:
        if not slug_dir.is_dir() or slug_dir.is_symlink():
            continue
        slug_name = slug_dir.name
        for run_file in sorted(slug_dir.glob("*.jsonl")):
            if run_file.is_symlink() or not run_file.is_file():
                continue
            # Cheaper than a second JSONL walk: reuse the existing
            # summarizer to detect in-flight (no ``run_end``) and to
            # pull ``started_at`` for the ``--since`` cutoff.
            summary = _summarize_run_log(run_file)
            if summary.get("unreadable"):
                continue
            if summary.get("duration") == "in-flight":
                runs_in_flight += 1
                continue
            if cutoff_dt is not None:
                started_at_str = summary.get("started_at")
                if not isinstance(started_at_str, str) or started_at_str == "?":
                    continue
                try:
                    started_dt = datetime.fromisoformat(started_at_str)
                except ValueError:
                    continue
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                if started_dt < cutoff_dt:
                    continue
            runs_scanned += 1
            all_samples.extend(
                _iter_call_samples(run_file, plan_slug=slug_name)
            )

    mode_filter: Optional[str] = args.mode
    if mode_filter is not None:
        all_samples = [s for s in all_samples if s.mode == mode_filter]

    groups = _group_samples(all_samples, args.by)
    summaries: list[tuple[str, dict[str, Any]]] = []
    for key, items in groups.items():
        s = _summarize_group(
            items, include_incomplete=args.include_incomplete,
        )
        summaries.append((key, s))
    # Largest total wall-clock first — alphabetical on ties keeps the
    # output stable across runs (and across the test snapshot).
    summaries.sort(
        key=lambda kv: (-(kv[1].get("total_ms") or 0), kv[0])
    )
    if args.top is not None and args.top > 0:
        summaries = summaries[: args.top]

    if args.json:
        out_payload = {
            "by": args.by,
            "runs_scanned": runs_scanned,
            "runs_in_flight_skipped": runs_in_flight,
            "groups": [
                {"key": key, **summary} for key, summary in summaries
            ],
        }
        print(json.dumps(out_payload, separators=(",", ":")))
        return 0

    if not summaries:
        print(f"no claude calls under {root}")
        return 0

    header = (
        f"{args.by:<32}  {'count':>6}  {'fail':>4}  {'incpl':>5}  "
        f"{'min':>8}  {'max':>8}  "
        f"{'p50':>8}  {'p95':>8}  {'mean':>8}  {'total':>8}  "
        f"{'cost($)':>9}  {'tok_in':>9}  {'tok_out':>9}  {'cache_rd':>9}"
    )
    print(header)
    for key, s in summaries:
        cost_v = s["cost_usd"]
        cost_s = "-" if cost_v is None else f"{float(cost_v):.4f}"
        tin = s["tokens_input"]
        tin_s = "-" if tin is None else str(tin)
        tout = s["tokens_output"]
        tout_s = "-" if tout is None else str(tout)
        cache = s["cache_reads"]
        cache_s = "-" if cache is None else str(cache)
        # The p50 / p95 sentinel uses count-minus-incomplete so a
        # bucket whose only samples are unmatched starts renders the
        # cells as ``-`` rather than ``n=0`` (which would duplicate
        # what the ``count`` / ``incpl`` columns already say).
        n_complete = s["count"] - s["incomplete"]
        # Truncate long keys (e.g. ``slug/run_id``) so the table
        # doesn't wrap and a visual scan still aligns the columns.
        key_disp = key if len(key) <= 32 else key[:31] + "…"
        print(
            f"{key_disp:<32}  {s['count']:>6}  {s['fail']:>4}  "
            f"{s['incomplete']:>5}  {_fmt_ms(s['min_ms']):>8}  "
            f"{_fmt_ms(s['max_ms']):>8}  "
            f"{_fmt_ms_or_n(s['p50_ms'], n_complete):>8}  "
            f"{_fmt_ms_or_n(s['p95_ms'], n_complete):>8}  "
            f"{_fmt_ms(s['mean_ms']):>8}  "
            f"{_fmt_ms(s['total_ms']):>8}  {cost_s:>9}  {tin_s:>9}  "
            f"{tout_s:>9}  {cache_s:>9}"
        )
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    """Inspect and manage on-disk run logs (state management).

    Mirrors :func:`cmd_checkpoint` in shape, error contract, and
    traversal hardening — and adds one new shape ``cmd_checkpoint``
    doesn't have: ``diff <a> <b>`` reads two JSONL files and renders a
    per-phase wall-clock + token-count delta table.

    Five actions, dispatched via ``args.action``:

    - ``list`` — summarize every run log under
      ``<repo>/.plan-tool/runs/`` (one row per ``<slug>/<run_id>.jsonl``).
    - ``show <slug>/<run_id>`` — print one run's events to stdout
      (metadata to stderr).
    - ``diff <a> <b>`` — render a per-phase delta table for two runs.
    - ``profile`` — aggregate ``claude_call_end`` events into a
      latency / cost report (by mode / step / run).
    - ``clear`` — delete run logs by slug, age, or wholesale (``--all``).

    Exit codes match :func:`cmd_checkpoint`:

    - ``0`` — success (including ``clear`` on a non-existent slug).
    - ``1`` — partial failure (``clear`` couldn't unlink some files,
      ``show`` / ``diff`` target missing or unreadable).
    - ``2`` — invalid arguments (traversal, missing ``--all`` / slug /
      ``--older-than`` on clear, missing slash in show/diff,
      unparseable ``--older-than``).
    """
    try:
        repo_root = _resolve_cmd_repo_root(args)
    except FileNotFoundError as exc:
        error(str(exc))
        return 2

    root = runs_root(repo_root)

    if args.action == "list":
        if not root.is_dir():
            print(f"no runs (root {root} does not exist)")
            return 0
        slug_filter: Optional[str] = getattr(args, "slug", None)
        if slug_filter is not None:
            err = _validate_checkpoint_arg(slug_filter, kind="slug")
            if err is not None:
                error(f"{err}")
                return 2
        rows: list[tuple[str, str, str, str, str, int, str]] = []
        if slug_filter is not None:
            slug_dirs = [run_dir(repo_root, slug_filter)]
        else:
            slug_dirs = sorted(
                p for p in root.iterdir()
                if p.is_dir() and not p.is_symlink()
            )
        for slug_dir in slug_dirs:
            if not slug_dir.is_dir() or slug_dir.is_symlink():
                continue
            for run_file in sorted(slug_dir.glob("*.jsonl")):
                if run_file.is_symlink() or not run_file.is_file():
                    continue
                info = _summarize_run_log(run_file)
                tokens_total = info["tokens_total"]
                if tokens_total is None:
                    tokens_str = "-"
                else:
                    tokens_str = str(tokens_total)
                rows.append(
                    (
                        slug_dir.name,
                        run_file.stem,
                        str(info["command"]),
                        str(info["started_at"]),
                        str(info["duration"]),
                        int(info["event_count"]),
                        tokens_str,
                    )
                )
        if not rows:
            print(f"no runs under {root}")
            return 0
        print(
            f"{'slug':<40}  {'run_id':<32}  {'cmd':<10}  "
            f"{'started_at':<22}  {'duration':>10}  {'events':>7}  "
            f"{'tokens':>8}"
        )
        for slug, rid, cmd, started, dur, count, toks in rows:
            print(
                f"{slug:<40}  {rid:<32}  {cmd:<10}  "
                f"{started:<22}  {dur:>10}  {count:>7}  {toks:>8}"
            )
        return 0

    if args.action == "show":
        slug, run_id, err = _parse_runs_target(args.target)
        if err is not None:
            error(f"{err}")
            return 2
        assert slug is not None and run_id is not None
        for value, kind in ((slug, "slug"), (run_id, "run_id")):
            verr = _validate_checkpoint_arg(value, kind=kind)
            if verr is not None:
                error(f"{verr}")
                return 2
        jsonl_path = run_log_path(repo_root, slug, run_id)
        if not _safe_under_root(jsonl_path, root):
            error(
                f"refusing to read outside {root} (resolved: "
                f"{jsonl_path})"
            )
            return 2
        if not jsonl_path.is_file() or jsonl_path.is_symlink():
            print(f"no such run: {jsonl_path}", file=sys.stderr)
            return 1
        try:
            events, skipped = _load_events_with_skips(jsonl_path)
        except OSError as exc:
            print(f"error reading {jsonl_path}: {exc}", file=sys.stderr)
            return 1
        # Hard fail when the file has only unparseable content — the
        # alternative would be to print metadata headers full of ``?``
        # and exit 0, which would let CI / scripts treat a corrupted
        # log as a successful read. A clean *empty* file (no
        # non-blank lines) is allowed through to the metadata branch
        # below (exits 0 with ``?`` headers) — that's a distinct
        # state, typically "the run died before its first event."
        if skipped > 0 and not events:
            error(
                f"{jsonl_path}: {skipped} unreadable line(s); "
                "no parseable events"
            )
            return 1
        if skipped > 0:
            warn(
                f"{skipped} unreadable line(s) skipped"
            )
        # Check schema_version on the first run_start event (if any).
        # The v1→v2 bump (and any future bump) is additive, so older
        # logs deserialize cleanly; only reject *newer*-than-known
        # logs whose fields we can't reason about.
        run_start = next(
            (e for e in events if e.get("event") == "run_start"), None
        )
        schema_in_file = (
            run_start.get("schema_version") if run_start else None
        )
        if (
            run_start is not None
            and isinstance(schema_in_file, int)
            and schema_in_file > RUN_LOG_SCHEMA_VERSION
        ):
            error(
                f"unsupported run-log schema_version (this build "
                f"knows {RUN_LOG_SCHEMA_VERSION}, file is "
                f"{schema_in_file!r}); refusing to render"
            )
            return 1
        if (
            isinstance(schema_in_file, int)
            and schema_in_file < RUN_LOG_SCHEMA_VERSION
        ):
            note(
                f"run-log schema_version is {schema_in_file} "
                f"(this build is {RUN_LOG_SCHEMA_VERSION}); rendering "
                f"as a best-effort view of the older format"
            )
        # Metadata header to stderr; events to stdout.
        meta_command = (
            run_start.get("command", "?") if run_start else "?"
        )
        meta_plan = (
            run_start.get("plan_slug", "?") if run_start else "?"
        )
        print(
            f"# run_id: {run_id}\n"
            f"# plan_slug: {meta_plan}\n"
            f"# command: {meta_command}\n"
            f"# schema_version: {schema_in_file if schema_in_file is not None else '?'}",
            file=sys.stderr,
        )
        depth = 0
        for ev in events:
            kind = ev.get("event", "?")
            ts = ev.get("ts", "")
            if isinstance(ts, str) and "T" in ts:
                tail = ts.split("T", 1)[1]
                # Trim TZ suffix for readability — keep HH:MM:SS only.
                hhmmss = tail.split("+")[0].split("Z")[0].split(".")[0]
            else:
                hhmmss = str(ts)
            if kind == "phase_end" and depth > 0:
                depth -= 1
            line_indent = "  " * depth
            extra_indent = ""
            if kind in ("claude_call_start", "claude_call_end") and depth > 0:
                extra_indent = "  "
            extras: list[str] = []
            for key in (
                # ``skip_reason`` qualifies ``outcome``: several phases
                # bucket distinct causes into ``skipped``, and without it
                # a deliberate saving is indistinguishable from a call
                # that ran and produced nothing.
                "phase", "duration_ms", "outcome", "skip_reason", "rc",
                "attempt", "step_id", "name", "failure_path",
            ):
                if key in ev and ev[key] is not None:
                    extras.append(f"{key}={ev[key]}")
            if kind in ("claude_call_end",):
                ti = ev.get("tokens_input")
                to = ev.get("tokens_output")
                if ti is None and to is None:
                    extras.append("tokens=-")
                else:
                    ti_s = "-" if ti is None else str(ti)
                    to_s = "-" if to is None else str(to)
                    extras.append(f"tokens={ti_s}/{to_s}")
            tail = ("  " + "  ".join(extras)) if extras else ""
            print(f"{line_indent}{extra_indent}{hhmmss}  {kind}{tail}")
            if kind == "phase_start":
                depth += 1
        return 0

    if args.action == "diff":
        parsed: list[tuple[str, str]] = []
        for label, target in (("a", args.a), ("b", args.b)):
            slug, run_id, err = _parse_runs_target(target)
            if err is not None:
                error(f"{label}: {err}")
                return 2
            assert slug is not None and run_id is not None
            for value, kind in ((slug, "slug"), (run_id, "run_id")):
                verr = _validate_checkpoint_arg(value, kind=kind)
                if verr is not None:
                    error(f"{label}: {verr}")
                    return 2
            parsed.append((slug, run_id))
        a_path = run_log_path(repo_root, parsed[0][0], parsed[0][1])
        b_path = run_log_path(repo_root, parsed[1][0], parsed[1][1])
        for label, p in (("a", a_path), ("b", b_path)):
            if not _safe_under_root(p, root):
                error(
                    f"{label}: refusing to read outside {root} "
                    f"(resolved: {p})"
                )
                return 2
        for label, p in (("a", a_path), ("b", b_path)):
            if not p.is_file() or p.is_symlink():
                error(f"{label}: no such run: {p}")
                return 1
        try:
            agg_a = _aggregate_run_for_diff(a_path)
            agg_b = _aggregate_run_for_diff(b_path)
        except OSError as exc:
            print(f"error reading run log: {exc}", file=sys.stderr)
            return 1
        schema_a = agg_a.pop("__schema__", {}).get("schema_version")
        schema_b = agg_b.pop("__schema__", {}).get("schema_version")
        # Additive bumps mean older logs are still readable; only newer-
        # than-known versions are unsafe to render.
        for label, sv in (("a", schema_a), ("b", schema_b)):
            if isinstance(sv, int) and sv > RUN_LOG_SCHEMA_VERSION:
                error(
                    f"{label}: unsupported run-log schema_version "
                    f"(this build knows {RUN_LOG_SCHEMA_VERSION}, file is "
                    f"{sv!r}); refusing to render"
                )
                return 1
        phases_a = set(agg_a.keys())
        phases_b = set(agg_b.keys())
        both = sorted(phases_a & phases_b)
        only_a = sorted(phases_a - phases_b)
        only_b = sorted(phases_b - phases_a)
        ordered = (
            [(p, "both") for p in both]
            + [(p, "only-in-A") for p in only_a]
            + [(p, "only-in-B") for p in only_b]
        )
        header = (
            f"{'phase':<30}  {'wall_a':>8}  {'wall_b':>8}  "
            f"{'Δwall':>8}  {'tokens_a':>9}  {'tokens_b':>9}  "
            f"{'Δtokens':>8}  flag"
        )
        print(header)
        total_d_wall = 0
        total_d_tokens = 0
        for phase, flag in ordered:
            a = agg_a.get(phase)
            b = agg_b.get(phase)

            def _wall_str(agg: Optional[dict[str, Any]]) -> str:
                if agg is None:
                    return "-"
                return str(int(agg["wall_ms"]))

            def _tokens_val(agg: Optional[dict[str, Any]]) -> Optional[int]:
                if agg is None:
                    return None
                if not agg["tokens_seen"]:
                    return None
                return int(agg["tokens_in"]) + int(agg["tokens_out"])

            def _tokens_str(agg: Optional[dict[str, Any]]) -> str:
                v = _tokens_val(agg)
                return "-" if v is None else str(v)

            wall_a_s = _wall_str(a)
            wall_b_s = _wall_str(b)
            tokens_a_v = _tokens_val(a)
            tokens_b_v = _tokens_val(b)
            tokens_a_s = _tokens_str(a)
            tokens_b_s = _tokens_str(b)
            if flag == "both":
                d_wall = int(b["wall_ms"]) - int(a["wall_ms"])
                total_d_wall += d_wall
                d_wall_s = f"{d_wall:+d}"
                if tokens_a_v is not None and tokens_b_v is not None:
                    d_tokens = tokens_b_v - tokens_a_v
                    total_d_tokens += d_tokens
                    d_tokens_s = f"{d_tokens:+d}"
                else:
                    d_tokens_s = "-"
                flag_s = ""
            else:
                d_wall_s = "-"
                d_tokens_s = "-"
                flag_s = flag
            print(
                f"{phase:<30}  {wall_a_s:>8}  {wall_b_s:>8}  "
                f"{d_wall_s:>8}  {tokens_a_s:>9}  {tokens_b_s:>9}  "
                f"{d_tokens_s:>8}  {flag_s}"
            )
        print(
            f"total Δwall: {total_d_wall:+d} ms · "
            f"total Δtokens: {total_d_tokens:+d} · "
            f"phases only-in-A: {len(only_a)} · "
            f"only-in-B: {len(only_b)}"
        )
        return 0

    if args.action == "profile":
        return _cmd_runs_profile(args, repo_root=repo_root, root=root)

    if args.action == "clear":
        # Allow combinations: --all alone, slug alone, --older-than
        # alone (root-wide age eviction), or slug + --older-than
        # (age eviction under one slug). Refuse only the "no signal"
        # case so a missing arg can't accidentally nuke the cache.
        if (
            not args.all_slugs
            and args.slug is None
            and args.older_than is None
        ):
            error(
                "clear requires --all, <slug>, or --older-than "
                "<DURATION> (e.g. plan-tool runs clear --older-than 30d)"
            )
            return 2
        cutoff_seconds: Optional[int] = None
        if args.older_than is not None:
            cutoff_seconds = _parse_duration_arg(args.older_than)
            if cutoff_seconds is None:
                error(
                    "--older-than expects e.g. 30d, 48h, 90m, or "
                    "a positive integer (seconds)"
                )
                return 2
        # When a slug is named, validate it. ``--all`` + slug is not
        # ambiguous — slug is ignored when ``--all`` is set, matching
        # ``cmd_checkpoint``'s "--all wins" stance.
        if args.slug is not None and not args.all_slugs:
            err = _validate_checkpoint_arg(args.slug, kind="slug")
            if err is not None:
                error(f"{err}")
                return 2
        if not root.is_dir():
            print(f"no runs to clear (root {root} does not exist)")
            return 0
        # Decide which slug dirs to walk.
        if args.all_slugs:
            slug_dirs = [
                p for p in root.iterdir()
                if p.is_dir() and not p.is_symlink()
            ]
            target_label = "all slugs"
        elif args.slug is not None:
            slug_dir = run_dir(repo_root, args.slug)
            if not _safe_under_root(slug_dir, root):
                error(
                    f"refusing to operate outside {root} "
                    f"(resolved: {slug_dir})"
                )
                return 2
            if slug_dir.is_symlink() or not slug_dir.is_dir():
                print(f"no runs for slug {args.slug!r}")
                return 0
            slug_dirs = [slug_dir]
            target_label = repr(args.slug)
        else:
            # --older-than alone → walk every non-symlinked slug.
            slug_dirs = [
                p for p in root.iterdir()
                if p.is_dir() and not p.is_symlink()
            ]
            target_label = "all slugs"
        removed = 0
        failed = 0
        # Under a TTL, ``in-flight.json`` is preserved (mtime is not a
        # reliable age proxy — the writer might still be active).
        # ``--all`` and bare-slug clears wipe it.
        wipe_in_flight = cutoff_seconds is None
        for slug_dir in slug_dirs:
            if slug_dir.is_symlink() or not slug_dir.is_dir():
                continue
            for run_file in slug_dir.glob("*.jsonl"):
                if run_file.is_symlink():
                    continue
                if not _is_run_evictable(run_file, cutoff_seconds):
                    continue
                try:
                    run_file.unlink()
                    removed += 1
                except OSError as exc:
                    failed += 1
                    warn(
                        f"could not remove {run_file}: {exc}"
                    )
            if wipe_in_flight:
                ifp = slug_dir / IN_FLIGHT_FILENAME
                if ifp.is_file() and not ifp.is_symlink():
                    try:
                        ifp.unlink()
                    except OSError as exc:
                        failed += 1
                        warn(
                            f"could not remove {ifp}: {exc}"
                        )
            try:
                slug_dir.rmdir()
            except OSError:
                pass
        # Raw stream logs are not tied to a run log's lifetime, so they
        # are pruned by their own age under the same cutoff.
        streams_removed = 0
        for slug_dir in slug_dirs:
            streams_removed += len(
                prune_stream_logs(slug_dir, older_than_seconds=cutoff_seconds)
            )
            try:
                slug_dir.rmdir()
            except OSError:
                pass
        if failed:
            print(
                f"removed {removed} run log file(s) for {target_label}; "
                f"{failed} could not be removed (see warnings above)"
            )
            return 1
        print(
            f"removed {removed} run log file(s) and {streams_removed} "
            f"stream log dir(s) for {target_label}"
        )
        return 0

    error(f"unknown runs action {args.action!r}")
    return 2


def register(subparsers) -> dict[str, Handler]:
    """Add the ``runs`` subparser (and its sub-actions) and return its map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    p_runs = sub.add_parser(
        "runs",
        help=(
            "inspect / manage on-disk run logs under "
            "<repo>/.plan-tool/runs/. Subactions: list / show / diff / "
            "profile / clear."
        ),
        parents=[yes_parent],
    )
    p_runs_sub = p_runs.add_subparsers(dest="action", required=True)

    p_runs_list = p_runs_sub.add_parser(
        "list",
        help="list every run log with slug, run_id, command, duration, tokens",
        parents=[yes_parent],
    )
    p_runs_list.add_argument(
        "--slug",
        default=None,
        help="limit the listing to a single plan slug",
    )

    p_runs_show = p_runs_sub.add_parser(
        "show",
        help=(
            "print one run log's events to stdout (metadata to stderr, "
            "event lines to stdout)"
        ),
        parents=[yes_parent],
    )
    p_runs_show.add_argument(
        "target",
        help=(
            "run identifier in the form <slug>/<run_id> "
            "(e.g. my-plan/2026-05-14T12-34-56-9f3a1c)"
        ),
    )

    p_runs_diff = p_runs_sub.add_parser(
        "diff",
        help=(
            "render a per-phase wall-clock + token-count delta table for "
            "two runs, flagging only-in-A / only-in-B phases"
        ),
        parents=[yes_parent],
    )
    p_runs_diff.add_argument("a", help="first run in the form <slug>/<run_id>")
    p_runs_diff.add_argument("b", help="second run in the form <slug>/<run_id>")

    p_runs_profile = p_runs_sub.add_parser(
        "profile",
        help=(
            "aggregate claude_call_end events into a latency / cost "
            "report (by mode, step, or run)"
        ),
        parents=[yes_parent],
    )
    p_runs_profile.add_argument(
        "--slug",
        default=None,
        help="limit profiling to a single plan slug",
    )
    p_runs_profile.add_argument(
        "--mode",
        default=None,
        help=(
            "filter to claude calls whose containing phase_start mode "
            "matches (e.g. run, check, reconcile, optimize)"
        ),
    )
    p_runs_profile.add_argument(
        "--since",
        default=None,
        metavar="DURATION",
        help=(
            "include only runs whose run_start ts is newer than DURATION "
            "(e.g. 30d, 48h, 90m, or seconds as integer)"
        ),
    )
    p_runs_profile.add_argument(
        "--by",
        choices=("mode", "step", "run"),
        default="mode",
        help="aggregation key (default: mode)",
    )
    p_runs_profile.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help=(
            "show only the top N groups by total wall-clock (after "
            "sorting; useful with --by step or --by run)"
        ),
    )
    p_runs_profile.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of the table renderer",
    )
    p_runs_profile.add_argument(
        "--include-incomplete",
        dest="include_incomplete",
        action="store_true",
        help=(
            "surface unmatched claude_call_start events (no end "
            "observed) in the incomplete column; they remain excluded "
            "from p50/p95 latency stats either way"
        ),
    )

    p_runs_clear = p_runs_sub.add_parser(
        "clear",
        help=(
            "delete run logs. Pass --all, a <slug>, or --older-than "
            "<DURATION>. Combine slug + --older-than to evict by age "
            "under one slug."
        ),
        parents=[yes_parent],
    )
    p_runs_clear.add_argument(
        "slug",
        nargs="?",
        default=None,
        help="plan slug whose runs to clear (omit when using --all or --older-than)",
    )
    p_runs_clear.add_argument(
        "--all",
        dest="all_slugs",
        action="store_true",
        help="clear every run log under the runs root",
    )
    p_runs_clear.add_argument(
        "--older-than",
        dest="older_than",
        default=None,
        metavar="DURATION",
        help=(
            "evict only runs whose run_start ts is older than DURATION "
            "(e.g. 30d, 48h, 90m, or seconds as integer; 30d is the "
            "recommended default)"
        ),
    )

    return {
        "runs": cmd_runs,
    }
