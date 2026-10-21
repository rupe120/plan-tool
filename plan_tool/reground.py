"""Re-ground primitives: the deterministic mark-done actuator and the gated
apply-or-recommend bridge that wraps it.

Two halves live here:

- **The actuator** — :func:`mark_steps_done`, a deterministic in-memory mutator
  that flips a set of already-built steps to ``status: done`` and re-establishes
  the run cursor once. No filesystem, git, or Claude touch — the bridge does the
  parse and write around it. Keeps every step id (no renumber), so unlike
  ``scope_out.compute_narrow`` / ``detail.merge_steps`` it needs no
  ``depends_on`` repair, detail migration, or ``repo_root``.
- **The bridge** — :func:`reground_bridge` (returning a frozen
  :class:`RegroundResult`): the fourth instance of the apply-or-recommend gate
  shape (after :func:`launcher.escalate_to_split`, :func:`scope_out.scope_out_step`,
  and ``detail.merge_bridge``), modelled closest on ``scope_out_step`` — like it,
  re-ground spends **zero Claude** and takes no ``invoker=`` seam.

This bridge is deliberately **not** merge: it never routes to ``plan-tool merge``
(that would conflate re-ground with structural merge). It mints no
``review.Recommendation`` and adds no new source token — the caller (the walk)
already holds the ``granularity-merge`` re-ground finding that fired it.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from plan_tool import locator
from plan_tool.parser import parse_plan, write_plan
from plan_tool.schema import Plan, PlanStatus, Step, StepScope, StepStatus
from plan_tool.scope_fence import (
    _strip_frontmatter,
    collapse_intent_to_one_line,
    extract_h2_sections,
    is_placeholder_intent,
    source_references_block,
)

# Re-ground dispositions: what the apply branch does with the flagged steps.
# ``mark-done`` (default) just flips them ``done``; ``re-baseline`` also writes
# a ``create --from-existing`` re-decompose seed first.
DISPOSITION_MARK_DONE = "mark-done"
DISPOSITION_REBASELINE = "re-baseline"


@dataclass(frozen=True)
class MarkDoneSummary:
    """What :func:`mark_steps_done` mutated in memory — lets the bridge build
    its :class:`RegroundResult` without re-inspecting the ``Plan``.

    ``marked_ids`` are the steps actually flipped ``done`` (ids already done are
    dropped, a no-op). ``new_current_id`` is the step promoted to ``current``
    when the mark left no cursor, else ``None``. ``completed`` is ``True`` when
    the mark took the plan to ``PlanStatus.COMPLETED``.
    """

    marked_ids: list[int]
    new_current_id: Optional[int] = None
    completed: bool = False


def mark_steps_done(plan: Plan, step_ids: list[int]) -> MarkDoneSummary:
    """Mark each named committed, not-yet-done step ``done`` and re-establish
    the run cursor — deterministic, in memory, no IO.

    This is strictly a lifecycle transition: every step keeps its existing
    ordered ``concept_ids`` ownership, including steps outside ``step_ids`` and
    steps that were already done.

    Skips ids already ``DONE`` (a no-op). After marking the whole set, the
    cursor is re-established **once** (not per step, mirroring
    :func:`launcher.mark_done_and_advance` and ``scope_out.compute_narrow``'s
    cursor/status blocks): if no ``CURRENT`` remains, promote the next runnable
    step; if none is promotable and every committed step is done, flip the plan
    to ``COMPLETED``. The ``next_runnable_step`` / ``all_steps_done`` rule stays
    single-sourced on the ``Plan`` model. The bridge parses and writes around
    this; the actuator itself assumes the ids are valid, committed steps (its
    caller :func:`reground_bridge` validates existence + scope first).
    """
    marked: list[int] = []
    for sid in sorted(set(step_ids)):
        step = plan.step_by_id(sid)
        if step.status is StepStatus.DONE:
            continue
        step.status = StepStatus.DONE
        marked.append(sid)

    # Re-establish the cursor once, after the whole set is marked.
    new_current_id: Optional[int] = None
    if plan.current_step() is None:
        nxt = plan.next_runnable_step()
        if nxt is not None:
            nxt.status = StepStatus.CURRENT
            new_current_id = nxt.id
        elif plan.all_steps_done:
            plan.status = PlanStatus.COMPLETED

    return MarkDoneSummary(
        marked_ids=marked,
        new_current_id=new_current_id,
        completed=plan.status is PlanStatus.COMPLETED,
    )


@dataclass(frozen=True)
class RegroundResult:
    """Disposition of one :func:`reground_bridge` call — the re-ground analog of
    :class:`scope_out.ScopeOutResult` / :class:`launcher.EscalateResult`.

    ``outcome`` is exactly one of five strings; only ``"applied"`` mutates:
      - ``"applied"`` — the named steps were marked ``done`` and the plan
        written; ``marked_ids`` / ``new_current_id`` / ``completed`` describe it.
        Under the ``re-baseline`` disposition ``seed_path`` also points at the
        ``create --from-existing`` seed written first; ``None`` for mark-done.
      - ``"recommended"`` — safe but not actuated (``allow_reground=False`` or a
        declined / non-TTY confirm); ``marked_ids`` shows the would-be set.
      - ``"unsafe"`` — a named step is parked (``deferred`` / ``wont_do``);
        ``blocking`` carries the parked ids.
      - ``"step-missing"`` — a named id is not in the plan; ``blocking`` carries
        the absent ids.
      - ``"noop"`` — nothing left to mark (empty input, or all already ``done``).

    Mints **no** ``review.Recommendation`` — the caller already holds the
    re-ground finding — which honors "no new source token" by carrying none.
    """

    outcome: str
    requested_ids: list[int]
    marked_ids: list[int] = field(default_factory=list)
    new_current_id: Optional[int] = None
    completed: bool = False
    blocking: list[int] = field(default_factory=list)
    seed_path: Optional[Path] = None


def reground_bridge(
    plan_path: Path,
    *,
    step_ids: list[int],
    allow_reground: bool,
    yes: bool = False,
    prompt_fn: Optional[Callable[[str], str]] = None,
    disposition: str = DISPOSITION_MARK_DONE,
    repo_root: Path | None = None,
) -> RegroundResult:
    """Apply-or-recommend the re-ground of a set of already-built steps a
    ``granularity-merge`` re-ground finding named.

    Two dispositions select what the apply branch does with the flagged set:
    ``mark-done`` (default) flips them ``done``; ``re-baseline`` additionally
    writes a ``create --from-existing`` re-decompose seed under ``plan-seeds/``
    **first** (so the durable artifact survives a failed plan write), then marks
    them done. ``repo_root`` is required for ``re-baseline`` (the seed's target
    dir) and unused by ``mark-done``. An unknown disposition is a programming
    error (raises ``ValueError``).

    The fourth instance of the apply-or-recommend gate shape, modelled on
    :func:`scope_out.scope_out_step`. Gate order — every refusal path and the
    default (recommend) mutate nothing and spend zero Claude (there is no
    ``invoker=`` seam):

      1. Re-parse the plan from disk — never trust an in-memory ``Plan``.
      2. Normalize ``step_ids`` to a sorted, distinct set.
      3. Existence gate: any id absent → ``"step-missing"`` (blocking ids).
      4. Safety gate: any named parked step → ``"unsafe"`` (blocking ids) —
         required, since ``schema.Step`` refuses a parked step set ``done`` and
         ``write_plan``'s re-validation would raise.
      5. No-op gate: after dropping ids already ``done``, nothing left →
         ``"noop"``.
      6. Opt-in gate: ``allow_reground=False`` → ``"recommended"``, no prompt.
      7. Confirm gate: non-TTY without ``yes`` auto-declines; a TTY prompt
         surfaces the flagged step ids/titles/files so the operator can verify
         builtness before the ``PENDING → DONE`` drop.
      8. Apply: mark the set done, ``write_plan`` (compare-and-swap safe — the
         same in-process parse recorded the provenance), return ``"applied"``.

    Never routes to ``plan-tool merge`` — the re-ground remedy is mark-done /
    re-baseline, not structural merge.
    """
    if disposition not in (DISPOSITION_MARK_DONE, DISPOSITION_REBASELINE):
        raise ValueError(f"unknown reground disposition: {disposition!r}")
    if disposition == DISPOSITION_REBASELINE and repo_root is None:
        raise ValueError(
            "reground_bridge(disposition='re-baseline') requires repo_root="
        )

    plan_path = Path(plan_path)
    plan = parse_plan(plan_path)
    requested = sorted({int(sid) for sid in step_ids})

    # 3. Existence gate — deterministic refusal, no prompt, no mutation.
    id_set = {s.id for s in plan.steps}
    missing = [sid for sid in requested if sid not in id_set]
    if missing:
        return RegroundResult(
            outcome="step-missing", requested_ids=requested, blocking=missing
        )

    # 4. Safety gate — a parked named step cannot be set done.
    parked = [
        sid
        for sid in requested
        if plan.step_by_id(sid).scope is not StepScope.COMMITTED
    ]
    if parked:
        return RegroundResult(
            outcome="unsafe", requested_ids=requested, blocking=parked
        )

    # 5. No-op gate — drop ids already done; nothing left ⇒ re-ground satisfied.
    to_mark = [
        sid
        for sid in requested
        if plan.step_by_id(sid).status is not StepStatus.DONE
    ]
    if not to_mark:
        return RegroundResult(outcome="noop", requested_ids=requested)

    # 6. Opt-in gate.
    if not allow_reground:
        return RegroundResult(
            outcome="recommended", requested_ids=requested, marked_ids=to_mark
        )

    # 7. Confirm gate.
    flagged = [plan.step_by_id(sid) for sid in to_mark]
    if not _confirm_reground(
        prompt_fn,
        plan_path=plan_path,
        flagged_steps=flagged,
        yes=yes,
        disposition=disposition,
    ):
        return RegroundResult(
            outcome="recommended", requested_ids=requested, marked_ids=to_mark
        )

    # 8. Apply branch. Under re-baseline the seed is written *first* — the
    # durable re-plannable artifact must survive even if the plan write fails
    # after it (mirrors scope_out_step's seed-first ordering).
    seed_path: Optional[Path] = None
    if disposition == DISPOSITION_REBASELINE:
        assert repo_root is not None  # validated above
        source_body = _strip_frontmatter(plan_path.read_text(encoding="utf-8"))
        source_references = extract_h2_sections(
            source_body, ignore_fenced_code=True
        ).get("references")
        seed = render_rebaseline_seed(
            plan=plan,
            flagged_ids=to_mark,
            source_path=plan_path,
            source_references=source_references,
        )
        seed_path = _rebaseline_seed_path(plan_path, to_mark, repo_root)
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(seed, encoding="utf-8")

    summary = mark_steps_done(plan, to_mark)
    write_plan(plan_path, plan)
    return RegroundResult(
        outcome="applied",
        requested_ids=requested,
        marked_ids=summary.marked_ids,
        new_current_id=summary.new_current_id,
        completed=summary.completed,
        seed_path=seed_path,
    )


def _confirm_reground(
    prompt_fn: Optional[Callable[[str], str]],
    *,
    plan_path: Path,
    flagged_steps: list[Step],
    yes: bool,
    disposition: str = DISPOSITION_MARK_DONE,
) -> bool:
    """Interactive re-ground confirm — the repo's destructive-verb idiom
    (mirrors :func:`scope_out._confirm_scope_out` / ``detail._confirm_merge``).

    ``yes`` → no prompt. A non-TTY run without ``yes`` prints a ``-y`` hint and
    declines, so an unattended caller never silently marks steps done. On a TTY,
    surface each flagged step's id / title / files plus the "confirm these steps
    really are built before re-baselining" caveat — this is the one gate guarding
    a false positive from silently skipping real implementation, since the mark
    removes these steps from ``run``'s work queue and the finding is a
    low-confidence heuristic. Return ``True`` only on ``y`` / ``yes``.
    """
    if yes:
        return True
    plan_slug = locator.slug_from_filename(plan_path)
    if not sys.stdin.isatty():
        print(
            f"  re-ground of {plan_slug} needs confirmation; re-run with -y to "
            "mark these steps done unattended.",
            file=sys.stderr,
        )
        return False
    confirm_fn = prompt_fn if prompt_fn is not None else input
    lines = [
        f"Re-ground {plan_slug} — mark these steps done "
        "(removes them from run's work queue):"
    ]
    for s in flagged_steps:
        files = ", ".join(s.all_files) or "no files"
        lines.append(f"  → {s.id}. {s.title} [{files}]")
    lines.append("Confirm these steps really are built before re-baselining.")
    if disposition == DISPOSITION_REBASELINE:
        lines.append(
            "A `plan-tool create --from-existing` re-baseline seed will also be "
            "written under plan-seeds/."
        )
    lines.append("Mark them done? [y/N]: ")
    try:
        answer = confirm_fn("\n".join(lines)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — plan left unchanged.", file=sys.stderr)
        return False
    return answer in ("y", "yes")


# --------------------------------------------------------------------------
# The re-baseline seed: a pure ``create --from-existing`` renderer.
# --------------------------------------------------------------------------


def render_rebaseline_seed(
    *,
    plan: Plan,
    flagged_ids: Sequence[int],
    source_path: Path,
    source_references: str | None = None,
) -> str:
    """Render a ``create --from-existing`` re-baseline seed for the flagged
    already-built steps.

    Pure deterministic string builder — no file IO, no ``invoker=``, no detail
    resolution (this leaf must not import :mod:`plan_tool.detail`, so it renders
    from ``Step`` frontmatter only, not per-step detail bodies). **Mirrors**
    :func:`scope_out.render_carved_seed`'s ``create --from-existing`` shape
    rather than importing it (``scope_out`` transitively pulls in ``detail``).

    Three sections carry the whole plan so a subset re-baseline loses no scope:
    the flagged steps render as **Done-context** (already implemented — the code
    is ground truth, do not re-plan), every remaining non-flagged, not-done
    committed step renders as **Scope to re-plan** (the work still to do), and
    every not-done deferred step renders as **Deferred (parked)** so gated,
    parked-but-promotable scope survives retiring the old plan.
    """
    flagged_set = sorted({int(i) for i in flagged_ids})
    id_list = ", ".join(str(i) for i in flagged_set)
    header = (
        "<!-- plan-tool reground rebaseline-seed\n"
        f"source: {source_path}\n"
        f"reground_steps: {id_list}\n"
        "-->"
    )

    flagged_steps = [plan.step_by_id(i) for i in flagged_set]
    flagged_lookup = set(flagged_set)
    remaining = [
        s
        for s in plan.steps
        if s.id not in flagged_lookup
        and s.status is not StepStatus.DONE
        and s.scope is StepScope.COMMITTED
    ]
    deferred = [
        s
        for s in plan.steps
        if s.id not in flagged_lookup
        and s.status is not StepStatus.DONE
        and s.scope is StepScope.DEFERRED
    ]

    lines: list[str] = [
        header,
        "",
        f"# Plan seed: re-baseline of {plan.title}",
        "",
        (
            "This is a `plan-tool create --from-existing` input. It re-decomposes "
            "the plan from current code: the **Done-context** steps below are "
            "already implemented (the code is the ground truth — do **not** "
            "re-plan them), and the **Scope to re-plan** steps are the work "
            "still to do."
        ),
        "",
    ]
    raw_plan_intent = plan.intent
    if raw_plan_intent is not None:
        plan_intent = collapse_intent_to_one_line(raw_plan_intent)
        if plan_intent and not is_placeholder_intent(plan_intent):
            lines.append(
                f"Source plan intent: {plan_intent}. The re-decomposition "
                "still serves that purpose."
            )
            lines.append("")

    lines.extend(_rebaseline_done_context_block(flagged_steps))
    lines.extend(_rebaseline_scope_block(remaining))
    lines.extend(_rebaseline_deferred_block(deferred))

    lines.extend(source_references_block(source_path, source_references))

    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Source plan: {source_path}")
    lines.append(f"- Re-grounded steps: {id_list}")
    lines.append("")

    return "\n".join(lines)


def _rebaseline_step_bullet(step: Step) -> str:
    """Render one step with optional intent / concept_ids suffixes.

    Suffix order is stable: ``intent`` first, then ``concept_ids``. Each
    suffix is omitted when absent so intent-free / ownership-free bullets
    stay byte-identical to the prior form. Fence non-values omit — the six
    TODO/TBD spellings :func:`is_placeholder_intent` owns.
    """
    files = ", ".join(step.all_files) or "no files"
    change = step.change_type.value if step.change_type else "unspecified"
    bullet = f"- step {step.id}: {step.title} [{files}] ({change})"
    suffixes: list[str] = []
    raw_intent = step.intent
    if raw_intent is not None:
        step_intent = collapse_intent_to_one_line(raw_intent)
        if step_intent and not is_placeholder_intent(step_intent):
            suffixes.append(f"intent: {step_intent}")
    if step.concept_ids:
        ownership = ", ".join(step.concept_ids)
        suffixes.append(f"concept_ids: [{ownership}]")
    if suffixes:
        bullet += " — " + " — ".join(suffixes)
    return bullet


def _rebaseline_done_context_block(flagged_steps: Sequence[Step]) -> list[str]:
    """Render the flagged already-built steps as don't-re-plan done-context."""
    out: list[str] = [
        "## Done-context (already implemented — do not re-plan)",
        "",
        (
            "Everything in this section is **already built** — the code is the "
            "ground truth for the re-baseline. Do **not** re-plan or "
            "re-implement it."
        ),
        "",
    ]
    out.extend(_rebaseline_step_bullet(s) for s in flagged_steps)
    out.append("")
    return out


def _rebaseline_scope_block(remaining: Sequence[Step]) -> list[str]:
    """Render every remaining non-flagged, not-done committed step as the scope
    to re-plan, so a subset re-baseline never drops unbuilt scope."""
    out: list[str] = ["## Scope to re-plan", ""]
    if not remaining:
        out.append(
            "_No remaining committed, not-done steps — the whole plan is "
            "already-built context._"
        )
        out.append("")
        return out
    out.append(
        "Re-decompose these still-to-build steps from current code:"
    )
    out.append("")
    out.extend(_rebaseline_step_bullet(s) for s in remaining)
    out.append("")
    return out


def _rebaseline_deferred_block(deferred: Sequence[Step]) -> list[str]:
    """Render every remaining not-done deferred step as parked scope, so gated,
    parked-but-promotable work survives retiring the old plan. Omitted when empty
    (an all-committed plan carries no parked scope)."""
    if not deferred:
        return []
    out: list[str] = ["## Deferred (parked)", ""]
    out.append(
        "These steps are parked behind a gate (not on the critical path). Carry "
        "them forward as deferred — do not promote them into active scope here:"
    )
    out.append("")
    out.extend(_rebaseline_step_bullet(s) for s in deferred)
    out.append("")
    return out


def _rebaseline_seed_path(
    plan_path: Path, flagged_ids: Sequence[int], repo_root: Path
) -> Path:
    """Derive a collision-safe
    ``plan-seeds/<plan-slug>-reground-<first>-<last>.md`` path under
    ``repo_root``, mirroring :func:`scope_out._carved_seed_path`.

    ``<plan-slug>`` comes from the filename (:class:`schema.Plan` has no
    ``slug``); the ``-reground-<first>-<last>`` stem encodes the flagged ids so
    a re-ground seed is distinguishable from a scope-out carved seed.
    **Never overwrites** an existing seed — a taken base path gets a ``-2``,
    ``-3``, … suffix until a free path is found."""
    ids = sorted({int(i) for i in flagged_ids})
    plan_slug = locator.slug_from_filename(plan_path)
    stem = f"{plan_slug}-reground-{ids[0]}-{ids[-1]}"
    seeds_dir = repo_root / "plan-seeds"
    candidate = seeds_dir / f"{stem}.md"
    n = 2
    while candidate.exists():
        candidate = seeds_dir / f"{stem}-{n}.md"
        n += 1
    return candidate
