"""Pure-logic core for iteration-budget bookkeeping and convergence checks.

Provides the primitives that steps 2--4 (cmd_create, cmd_detail, cmd_run)
each wrap around their own claude-invocation loop: an ``IterativeBudget``
configuration, a mutable ``ConvergenceState`` carrying finding-set history,
the ``finding_set_delta`` set-algebra helper, the ``is_marginal`` plateau
detector, and the ``should_continue`` stop predicate.

This module is intentionally narrow:

- no claude shell-out (orchestrator-level concern; lives in callers),
- no CLI surface (``--iterate`` / ``--max-iterations`` flags land in step 5),
- no first-party ``plan_tool.*`` imports (keeps the dependency graph a tree
  and lets callers in steps 2/3/4 wire in parallel without load-order cycles),
- no third-party dependencies (stdlib-only).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable


if TYPE_CHECKING:
    from plan_tool.review import Recommendation


# Default ceiling on per-loop claude-invocation rounds. The 2x case
# (``cmd_detail`` / ``cmd_run`` reconcile cost ~2 claude calls per
# iteration — audit + apply — and ``cmd_completeness`` is 2x since the
# plan-audit pass landed) gets ~1.5 effective convergence rounds at
# max=3; the 1x case (``cmd_create``) gets 3 rounds. This trades the
# extra headroom of the old max=5 for lower token/wall-clock cost,
# since most loops converge or stall well before the cap anyway.
#
# Operators wanting more headroom can pass ``--max-iterations N`` to
# override per-invocation.
DEFAULT_MAX_ITERATIONS = 3

DEFAULT_ITERATION_BUDGET_SECONDS = 1800


def larger_iteration_budget_seconds(budget_seconds: int) -> int:
    """A ``--iteration-budget`` value above ``budget_seconds`` for resume hints.

    Doubles the effective deadline; the default is the floor so a deadline set
    below it never hints at a value lower than the default.
    """
    return max(2 * budget_seconds, DEFAULT_ITERATION_BUDGET_SECONDS)


MARGINAL_OVERLAP_THRESHOLD = 0.5

# Default number of consecutive no-net-progress rounds tolerated before
# ``should_continue`` fires ``"no_progress"``. See ``IterativeBudget``.
DEFAULT_MAX_STALL_ROUNDS = 2


BLOCKING_SEVERITIES: frozenset[str] = frozenset({"medium", "high", "critical"})

STAGE_BARE = "bare"
STAGE_DETAIL = "detail"

CONCEPTUAL_SOURCES: frozenset[str] = frozenset(
    {"plan-correctness", "plan-completeness"}
)
_VALID_STAGES: frozenset[str] = frozenset({STAGE_BARE, STAGE_DETAIL})


def is_blocking(severity: str) -> bool:
    """Return True for severities that should block iteration exit.

    "Blocking" means at least ``medium``. ``nit`` and ``info``
    findings are advisory and shouldn't keep the loop running on
    their own. Used by iteration loops to set
    ``ConvergenceState.has_blocking_findings`` so ``should_continue``
    can fire the ``"no_blocking_findings"`` early-exit.
    """
    return severity.lower() in BLOCKING_SEVERITIES


def _is_blocking_impact_baseline(rec: Recommendation) -> bool:
    """Return the baseline severity-or-high-impact blocking decision.

    High-impact advisory recommendations block iteration exit, while every
    existing severity-based block remains blocking regardless of impact.
    """
    return rec.impact == "high" or is_blocking(rec.severity)


def _medium_conceptual_docs_domain(
    rec: Recommendation,
    classify_domain: Callable[[Recommendation], str] | None,
) -> bool:
    """True for a medium-severity conceptual finding classified ``"docs"``.

    Shared by :func:`is_blocking_impact` and :func:`is_blocking_finding` so
    the docs exemption can't drift between them. ``False`` (never exempt)
    when ``classify_domain`` is omitted -- fail-safe, matches both callers'
    conservative default. See docs/how-to/pipeline/audit.md's "Conceptual bar set" and
    "Calibrated impact-aware convergence" for the rationale.
    """
    if classify_domain is None:
        return False
    if rec.source not in CONCEPTUAL_SOURCES:
        return False
    if rec.severity.lower() != "medium":
        return False
    return classify_domain(rec) == "docs"


def is_blocking_impact(
    rec: Recommendation,
    *,
    demote_low_impact_medium: Callable[[Recommendation], bool] | None = None,
    classify_domain: Callable[[Recommendation], str] | None = None,
) -> bool:
    """Return True when a recommendation blocks convergence.

    ``demote_low_impact_medium`` may opt out only an explicit low-impact,
    medium-severity baseline block. High-impact and high/critical-severity
    findings always block; advisory findings never consult either callback.
    ``classify_domain`` applies :func:`_medium_conceptual_docs_domain`'s
    exemption; reconcile-loop callers omit it deliberately (see
    docs/how-to/pipeline/audit.md).
    """
    if rec.impact == "high":
        return True
    if rec.severity in {"high", "critical"}:
        return True
    if _medium_conceptual_docs_domain(rec, classify_domain):
        return False
    if (
        rec.impact == "low"
        and rec.severity == "medium"
        and demote_low_impact_medium is not None
    ):
        return not demote_low_impact_medium(rec)
    return _is_blocking_impact_baseline(rec)


def is_blocking_finding(
    rec: Recommendation,
    *,
    stage: str,
    classify_domain: Callable[[Recommendation], str] | None = None,
) -> bool:
    """Return True when a conceptual finding blocks under the audit-stage bar.

    Non-conceptual findings use ``is_blocking(severity)`` only. ``nit``/
    ``info`` never block; ``high``/``critical`` always block. Bare-stage
    ``plan-completeness`` medium never blocks, independent of domain
    (detail-level completeness is judged once the detail bundle exists).
    Every other medium finding blocks unless
    :func:`_medium_conceptual_docs_domain` exempts it -- same rule at both
    stages; see docs/how-to/pipeline/audit.md's "Conceptual bar set" for why bare stage
    doesn't get a separate ``"unknown"`` carve-out.
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"invalid stage: {stage!r}")

    if rec.source not in CONCEPTUAL_SOURCES:
        return is_blocking(rec.severity)

    severity = rec.severity.lower()
    if severity in {"nit", "info"}:
        return False

    if severity in {"high", "critical"}:
        return True

    if severity != "medium":
        return False

    if stage == STAGE_BARE and rec.source == "plan-completeness":
        return False

    return not _medium_conceptual_docs_domain(rec, classify_domain)


@dataclass(frozen=True)
class IterativeBudget:
    """Configuration for one iteration loop.

    ``max_iterations`` caps the number of claude-invocation rounds.
    ``budget_seconds`` is a *debounced no-progress deadline*, not a cap
    on total loop wall-clock: it fires only once ``budget_seconds``
    have elapsed since the last recorded unit of forward progress
    (``record_iteration`` / ``touch``), checked between rounds -- an
    in-flight claude call, even a 15-20+ minute ``apply_finding``, is
    always allowed to finish, and its completion resets the timer. A
    steadily-progressing loop can run far longer than ``budget_seconds``
    in total; see ``ConvergenceState.last_activity_at`` for the debounce
    mechanics and ``hard_budget_seconds`` below for the non-debounced
    total-elapsed cap this is deliberately distinct from.
    ``enabled`` is the kill-switch for ``--no-iterate``: when False,
    callers should perform exactly one claude pass and skip the
    convergence loop entirely.

    ``hard_budget_seconds`` is the **cooperative wall-clock cap** (BACKLOG
    #123): a *non-debounced* total-elapsed deadline (measured from
    ``op_started_at``) that stops the loop at the next round boundary even
    while still making progress, so the op lands cleanly before an external
    ceiling instead of being SIGKILL'd mid-call. Distinct from the debounced
    ``budget_seconds`` stall deadline. ``0`` (default) disables it — no clock
    consulted, behavior unchanged. See ``docs/how-to/recovery/README.md`` for the full
    contrast and the granularity floor (BACKLOG #124).

    ``max_stall_rounds`` is the net-progress safety valve. Convergence
    is detected by comparing finding-*ID* sets across rounds, but a
    subjective claude audit (plan-audit, reconcile) re-phrases the same
    concept each round, minting a fresh content-hash id every time --
    so the ID-overlap checks (``is_marginal`` / ``"converged"``) never
    fire and the loop burns to ``max_iterations``. This counts rounds
    where the open-finding *count* did not strictly shrink and stops
    once that streak hits the threshold, regardless of whether the IDs
    line up. ``0`` disables the check (legacy behavior); the default
    ``2`` means "two consecutive rounds with no net progress -> stop".
    """

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    budget_seconds: int = DEFAULT_ITERATION_BUDGET_SECONDS
    enabled: bool = True
    max_stall_rounds: int = DEFAULT_MAX_STALL_ROUNDS
    hard_budget_seconds: int = 0
    # Runtime anchor (NOT user config) for the hard cap: a ``time.monotonic()``
    # reading stamped once at op entry (`_resolve_iterative_budget`) so the cap
    # measures TOTAL op wall-clock, surviving the per-step budget rebuilds
    # ``detail`` does. ``None`` falls back to per-loop ``started_at``.
    op_started_at: float | None = None

    def __post_init__(self) -> None:
        if self.max_iterations < 0:
            raise ValueError(
                f"max_iterations must be >= 0, got {self.max_iterations}"
            )
        if self.budget_seconds < 0:
            raise ValueError(
                f"budget_seconds must be >= 0, got {self.budget_seconds}"
            )
        if self.max_stall_rounds < 0:
            raise ValueError(
                f"max_stall_rounds must be >= 0, got {self.max_stall_rounds}"
            )
        if self.hard_budget_seconds < 0:
            raise ValueError(
                f"hard_budget_seconds must be >= 0, got {self.hard_budget_seconds}"
            )


@dataclass
class ConvergenceState:
    """Mutable bookkeeping for one in-flight iteration loop.

    ``iteration`` is the 1-indexed round counter (round 1 is the first
    post-initial-pass loop iteration -- the initial claude call that
    produces the artifact is round 0 by convention and isn't counted
    against ``max_iterations``).

    ``previous_finding_ids`` holds the set of finding IDs surfaced by
    the prior iteration's review pass; ``current_finding_ids`` holds
    the latest. ``record_iteration`` advances both atomically and
    refreshes ``last_activity_at`` so the budget timer debounces on
    forward progress.

    ``started_at`` is captured at construction (for total-elapsed
    logging) and never moves. ``last_activity_at`` is the *debounced*
    timestamp used by ``should_continue`` -- it resets every time
    ``record_iteration`` or ``touch`` is called, so a single
    long-running ``apply_finding`` (10-15 min is normal) won't
    spuriously trip the deadline as long as the loop is making
    progress. Tests inject ``now_fn`` to make the check deterministic.

    NOTE: ``last_activity_at`` is stamped at construction. A caller that
    does minutes-long round-0 work (an up-front claude audit/scan)
    *between* constructing the state and its first ``should_continue``
    must ``touch(state)`` after that work, or the deadline can fire at
    iteration 0 before the loop applies anything. Round-0 work is
    excluded from ``max_iterations``; the budget timer must match.
    """

    budget: IterativeBudget
    iteration: int = 0
    previous_finding_ids: frozenset[str] = field(default_factory=frozenset)
    current_finding_ids: frozenset[str] = field(default_factory=frozenset)
    started_at: float = field(default_factory=time.monotonic)
    last_activity_at: float = field(default_factory=time.monotonic)
    # When True, the current iteration's findings include at least one
    # medium+ severity. When False (and iteration > 0), should_continue
    # fires "no_blocking_findings" so the loop doesn't churn on
    # advisory nit/info-only rounds. Defaults True so callers that
    # don't update this field keep the pre-existing behavior.
    has_blocking_findings: bool = True
    # Count of consecutive rounds whose open-finding count did NOT
    # strictly shrink versus the prior round. Advanced by
    # ``record_iteration`` (reset to 0 on any net reduction, and on the
    # seed roll where ``previous_finding_ids`` is still empty so the
    # first real comparison isn't pre-charged). ``should_continue``
    # reads it for the ``"no_progress"`` stop. See
    # ``IterativeBudget.max_stall_rounds``.
    stall_rounds: int = 0


def finding_set_delta(
    previous: Iterable[str], current: Iterable[str]
) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Return ``(introduced, resolved, persisted)`` ID-set deltas.

    Mirrors the set algebra in ``launcher._compute_findings_delta`` but
    on raw ID strings rather than ``Recommendation`` tuples, so the same
    primitive serves both apply-finding's regression check and the
    iteration loop's progress check.
    """
    prev_set = frozenset(previous)
    curr_set = frozenset(current)
    introduced = curr_set - prev_set
    resolved = prev_set - curr_set
    persisted = curr_set & prev_set
    return introduced, resolved, persisted


def is_marginal(
    state: ConvergenceState,
    *,
    threshold: float = MARGINAL_OVERLAP_THRESHOLD,
) -> bool:
    """True when the current iteration's findings overlap the previous
    iteration's by at least ``threshold`` (fraction of *current* set).

    Decision rule:
      - empty current set -> not marginal (converged; the caller's
        convergence check on "current_finding_ids is empty" wins
        before this is consulted).
      - empty previous set with non-empty current -> not marginal
        (the first post-pass iteration has nothing to compare against).
      - otherwise: |current intersect previous| / |current| >= threshold.
    """
    if not state.current_finding_ids:
        return False
    if not state.previous_finding_ids:
        return False
    overlap = state.current_finding_ids & state.previous_finding_ids
    return (len(overlap) / len(state.current_finding_ids)) >= threshold


def should_continue(
    state: ConvergenceState,
    *,
    now_fn: Callable[[], float] = time.monotonic,
) -> tuple[bool, str]:
    """Decide whether to run another iteration.

    Returns ``(continue?, reason)`` so callers can log a one-line
    "stopped because deadline_exceeded" / "stopped because converged"
    line without re-deriving the predicate. Reason codes are stable
    strings the test suite asserts against:

      - ``"disabled"`` -- budget.enabled is False (--no-iterate)
      - ``"max_iterations"`` -- state.iteration >= budget.max_iterations and
        the latest scan still has open findings
      - ``"deadline_exceeded"`` -- wall-clock past
        ``last_activity_at + budget_seconds`` (debounced -- the timer
        resets on every ``record_iteration``/``touch`` call, so the
        deadline really means "no forward progress for this long")
      - ``"converged"`` -- current_finding_ids is empty
      - ``"no_blocking_findings"`` -- only advisory (nit/info) findings
        remain. Set by callers via
        ``state.has_blocking_findings = any(is_blocking(r.severity)
        for r in current_findings)`` before each ``should_continue``
        check. Fires only after the first iteration so a round-0 plan
        with only advisory findings still gets one apply pass.
      - ``"marginal"`` -- is_marginal(state) is True
      - ``"no_progress"`` -- the open-finding count failed to strictly
        shrink for ``budget.max_stall_rounds`` consecutive rounds
        (``record_iteration`` maintains ``state.stall_rounds``). This is
        the ID-agnostic backstop for the case ``is_marginal`` /
        ``"converged"`` can't catch: a subjective claude audit that
        re-phrases the same findings every round, minting fresh
        content-hash ids so the set-overlap checks never trip. Disabled
        when ``max_stall_rounds`` is 0.
      - ``"time_budget_exceeded"`` -- the cooperative wall-clock cap
        (``budget.hard_budget_seconds``, BACKLOG #123): elapsed past the hard
        budget, measured from ``budget.op_started_at`` when set (the op-level
        total-elapsed anchor) else the per-loop ``started_at``. Checked
        **last**, so a loop that would otherwise stop for a natural reason
        (converged / marginal / max_iterations / …) reports that reason
        instead; this fires only to preempt a round that *would continue*.
        Non-debounced (its anchor never moves), so it stops even a
        steadily-progressing loop. Disabled when ``hard_budget_seconds`` is 0.
      - ``"continue"`` -- none of the above; caller runs another round
    """
    if not state.budget.enabled:
        return False, "disabled"
    if state.iteration > 0 and not state.current_finding_ids:
        return False, "converged"
    if state.iteration >= state.budget.max_iterations:
        return False, "max_iterations"
    if (now_fn() - state.last_activity_at) >= state.budget.budget_seconds:
        return False, "deadline_exceeded"
    if state.iteration > 0 and not state.has_blocking_findings:
        return False, "no_blocking_findings"
    if state.iteration > 0 and is_marginal(state):
        return False, "marginal"
    if (
        state.budget.max_stall_rounds
        and state.iteration > 0
        and state.stall_rounds >= state.budget.max_stall_rounds
    ):
        return False, "no_progress"
    # Cooperative hard wall-clock cap (#123), checked LAST so natural stops
    # keep their reason. Anchored on the op-level ``op_started_at`` when set
    # (so a multi-step op measures TOTAL elapsed, not per-step), else the
    # per-loop ``started_at``; both never move, so this is a true elapsed cap,
    # not the debounced no-progress deadline above. Preempts only a round that
    # would otherwise continue.
    if state.budget.hard_budget_seconds:
        anchor = (
            state.budget.op_started_at
            if state.budget.op_started_at is not None
            else state.started_at
        )
        if (now_fn() - anchor) >= state.budget.hard_budget_seconds:
            return False, "time_budget_exceeded"
    return True, "continue"


def touch(
    state: ConvergenceState,
    *,
    now_fn: Callable[[], float] = time.monotonic,
) -> None:
    """Refresh ``state.last_activity_at`` to debounce the deadline timer.

    Call after any significant unit of work (a completed
    ``apply_finding``, a long claude subprocess return, etc.) so the
    budget_seconds deadline behaves as "no progress for this long"
    rather than "total wall clock from loop start". ``record_iteration``
    calls this automatically.
    """
    state.last_activity_at = now_fn()


def record_iteration(
    state: ConvergenceState, finding_ids: Iterable[str]
) -> None:
    """Atomically advance the iteration counter and roll the finding
    sets forward. Refreshes ``last_activity_at`` so the deadline
    debounces on iteration completion. Callers invoke this *after*
    completing one claude round and re-running the deterministic
    review primitives.

    Also maintains ``stall_rounds`` for the ``"no_progress"`` stop:
    a round counts as a stall when the new open-finding set is
    non-empty and did not strictly shrink versus the prior round. The
    seed roll (previous set still empty) and any round that converges
    to empty reset the streak to 0, so neither pre-charges the stall
    counter.
    """
    prev = state.current_finding_ids
    curr = frozenset(finding_ids)
    state.previous_finding_ids = prev
    state.current_finding_ids = curr
    state.iteration += 1
    if prev and curr and len(curr) >= len(prev):
        state.stall_rounds += 1
    else:
        state.stall_rounds = 0
    state.last_activity_at = time.monotonic()
