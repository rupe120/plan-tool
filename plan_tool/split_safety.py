"""Run-state safety check for splitting a plan step.

A ``schema``-only leaf so read-only consumers — the ``split-criteria`` per-plan
evaluator and the ``escalate_to_split`` bridge — can ask "is this step
splittable right now?" without importing the heavy ``detail`` orchestrator.
See BACKLOG relocation note: the check is a pure predicate, not orchestration.
"""

from __future__ import annotations

from plan_tool.schema import Plan, StepStatus


def split_is_safe(plan: Plan, target_id: int) -> tuple[bool, list[int]]:
    """Whether step ``target_id`` can be split without orphaning run state.

    A split renumbers every step from ``target_id`` onward. The only durable,
    id-keyed run state a renumber orphans is a ``DONE`` step's — its
    ``step N green`` commit subject and completion status. A ``DONE`` step at
    or after the target therefore blocks; everything else renumbers cleanly,
    **including a ``CURRENT`` step**: ``current`` means "next runnable" after
    ``create``/``detail`` authoring, not "mid-execution" (a ``CURRENT`` step
    never has a green commit — green ⟹ ``DONE``), so a freshly-authored plan
    can split its current step. A parked (``scope: deferred``/``wont_do``)
    step is still ``PENDING`` and carries no run state. Merely-*detailed*
    downstream steps stay safe: their detail files are renamed by
    ``detail._migrate_downstream_details_after_split``.

    Accepted residual risk: the ``_persist_step_completion`` SIGKILL window
    (``launcher.py``) can leave a step ``CURRENT`` on disk with a landed
    ``step N:`` lesson but no ``DONE`` flip. Splitting then renumbers that
    lesson's step reference. The window is narrow and the fallout soft
    (advisory prior-step context), so the gate does not re-add run-log/lesson
    I/O to catch it — that per-step run-evidence signal proved unsound (written
    by ``detail``/``create`` too, keyed to pre-renumber ids, TTL-evictable).

    Returns ``(safe, blocking_ids)`` so the caller can name what blocked
    the split when it declines.
    """
    blocking = sorted(
        s.id
        for s in plan.steps
        if s.id >= target_id and s.status == StepStatus.DONE
    )
    return (not blocking, blocking)
