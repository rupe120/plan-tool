"""Unit tests for the re-ground primitives: the deterministic mark-done
actuator (:func:`mark_steps_done`) and the gated apply-or-recommend bridge
(:func:`reground_bridge`)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from plan_tool.create import validate_from_existing_seed
import plan_tool.reground as reground
from plan_tool.parser import _coerce_enums, parse_plan
from plan_tool.reground import (
    MarkDoneSummary,
    RegroundResult,
    mark_steps_done,
    reground_bridge,
    render_rebaseline_seed,
)
from plan_tool.schema import (
    Plan,
    PlanStatus,
    Priority,
    Step,
    StepScope,
    StepStatus,
)


CONCEPT_A = "a" * 64
CONCEPT_B = "b" * 64
CONCEPT_C = "c" * 64


def _plan(
    steps: list[Step],
    status: PlanStatus = PlanStatus.IN_PROGRESS,
    *,
    intent: str | None = None,
) -> Plan:
    return Plan(
        title="Re-ground plan",
        status=status,
        priority=Priority.MEDIUM,
        steps=steps,
        intent=intent,
    )


def _step(
    id: int,
    *,
    status: StepStatus = StepStatus.PENDING,
    scope: StepScope = StepScope.COMMITTED,
    depends_on: list[int] | None = None,
    files: list[str] | None = None,
    concept_ids: list[str] | None = None,
    intent: str | None = None,
) -> Step:
    return Step(
        id=id,
        title=f"Step {id}",
        status=status,
        scope=scope,
        depends_on=depends_on or [],
        files=files or [],
        concept_ids=concept_ids or [],
        intent=intent,
    )


def _write_plan_file(tmp_path: Path, plan: Plan, name: str = "2-reground.md") -> Path:
    dumped = _coerce_enums(plan.model_dump(exclude_defaults=True, exclude_none=True))
    fm = yaml.safe_dump(
        dumped, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    path = tmp_path / name
    path.write_text(
        f"---\n{fm}---\n\nPlan prose body that survives re-grounding.\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------
# Actuator: mark_steps_done (deterministic, in memory, no IO).
# --------------------------------------------------------------------------


def test_marks_named_steps_done():
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2), _step(3)])
    summary = mark_steps_done(plan, [1, 2])
    assert plan.step_by_id(1).status is StepStatus.DONE
    assert plan.step_by_id(2).status is StepStatus.DONE
    assert isinstance(summary, MarkDoneSummary)
    assert summary.marked_ids == [1, 2]


def test_skips_ids_already_done():
    plan = _plan([_step(1, status=StepStatus.DONE), _step(2, status=StepStatus.CURRENT)])
    summary = mark_steps_done(plan, [1])
    assert plan.step_by_id(1).status is StepStatus.DONE
    assert summary.marked_ids == []  # already done ⇒ no-op


def test_promotes_next_when_current_marked_done():
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2), _step(3)])
    summary = mark_steps_done(plan, [1])
    assert plan.step_by_id(2).status is StepStatus.CURRENT
    assert summary.new_current_id == 2


def test_no_promote_when_another_current_remains():
    plan = _plan([_step(1), _step(2, status=StepStatus.CURRENT), _step(3)])
    summary = mark_steps_done(plan, [1])
    # step 2 is still current; marking a non-current step promotes nothing.
    assert plan.step_by_id(2).status is StepStatus.CURRENT
    assert summary.new_current_id is None
    currents = [s.id for s in plan.steps if s.status is StepStatus.CURRENT]
    assert currents == [2]


def test_flips_completed_when_all_committed_done():
    plan = _plan(
        [_step(1, status=StepStatus.DONE), _step(2, status=StepStatus.CURRENT)]
    )
    summary = mark_steps_done(plan, [2])
    assert plan.status is PlanStatus.COMPLETED
    assert summary.completed is True
    assert summary.new_current_id is None


def test_actuator_touches_no_disk(tmp_path):
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2), _step(3)])
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    mark_steps_done(plan, [1, 2])
    assert path.read_text(encoding="utf-8") == before


def test_mark_steps_done_preserves_concept_ids():
    plan = _plan(
        [
            _step(
                1,
                status=StepStatus.CURRENT,
                concept_ids=[CONCEPT_B, CONCEPT_A],
            ),
            _step(2, concept_ids=[CONCEPT_C]),
            _step(3, concept_ids=[CONCEPT_A]),
        ]
    )

    mark_steps_done(plan, [1, 2])

    assert [step.concept_ids for step in plan.steps] == [
        [CONCEPT_B, CONCEPT_A],
        [CONCEPT_C],
        [CONCEPT_A],
    ]


def test_mark_steps_done_preserves_intents():
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="marked why"),
            _step(2, intent="also marked"),
            _step(3, intent="unmarked why"),
        ]
    )
    before = [s.intent for s in plan.steps]
    mark_steps_done(plan, [1, 2])
    assert [s.intent for s in plan.steps] == before
    assert plan.step_by_id(1).status is StepStatus.DONE
    assert plan.step_by_id(2).status is StepStatus.DONE
    assert plan.step_by_id(3).intent == "unmarked why"


def test_cursor_promotion_preserves_all_concept_ids():
    plan = _plan(
        [
            _step(1, status=StepStatus.DONE, concept_ids=[CONCEPT_A]),
            _step(2, status=StepStatus.CURRENT, concept_ids=[CONCEPT_B]),
            _step(3, concept_ids=[CONCEPT_C, CONCEPT_A]),
        ]
    )

    mark_steps_done(plan, [2])

    assert plan.step_by_id(3).status is StepStatus.CURRENT
    assert [step.concept_ids for step in plan.steps] == [
        [CONCEPT_A],
        [CONCEPT_B],
        [CONCEPT_C, CONCEPT_A],
    ]


# --------------------------------------------------------------------------
# Bridge: reground_bridge gate matrix.
# --------------------------------------------------------------------------


def _built_plan_file(tmp_path: Path) -> Path:
    """A 3-step plan whose first two steps are already-built (mark-done targets)."""
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2), _step(3)])
    return _write_plan_file(tmp_path, plan)


def test_recommended_when_not_allowed(tmp_path):
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(path, step_ids=[1, 2], allow_reground=False)
    assert result.outcome == "recommended"
    assert result.marked_ids == [1, 2]  # the would-be set
    assert path.read_text(encoding="utf-8") == before


def test_recommended_when_non_tty_without_yes(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(path, step_ids=[1, 2], allow_reground=True, yes=False)
    assert result.outcome == "recommended"
    assert path.read_text(encoding="utf-8") == before


def test_recommended_when_confirm_declined(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=False,
        prompt_fn=lambda _msg: "n",
    )
    assert result.outcome == "recommended"
    assert path.read_text(encoding="utf-8") == before


def test_applies_on_yes_bypass(tmp_path):
    path = _built_plan_file(tmp_path)
    result = reground_bridge(path, step_ids=[1, 2], allow_reground=True, yes=True)
    assert result.outcome == "applied"
    assert result.marked_ids == [1, 2]
    reparsed = parse_plan(path)
    assert reparsed.step_by_id(1).status is StepStatus.DONE
    assert reparsed.step_by_id(2).status is StepStatus.DONE


def test_bridge_round_trip_preserves_concept_ids(tmp_path):
    plan = _plan(
        [
            _step(
                1,
                status=StepStatus.CURRENT,
                concept_ids=[CONCEPT_B, CONCEPT_A],
            ),
            _step(2, concept_ids=[CONCEPT_C]),
            _step(3, concept_ids=[CONCEPT_A]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)

    result = reground_bridge(path, step_ids=[1, 2], allow_reground=True, yes=True)

    assert result.outcome == "applied"
    reparsed = parse_plan(path)
    assert [step.concept_ids for step in reparsed.steps] == [
        [CONCEPT_B, CONCEPT_A],
        [CONCEPT_C],
        [CONCEPT_A],
    ]


def test_applies_on_tty_confirm_yes(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=False,
        prompt_fn=lambda _msg: "y",
    )
    assert result.outcome == "applied"
    assert parse_plan(path).step_by_id(2).status is StepStatus.DONE


def test_step_missing_when_id_absent(tmp_path):
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    # An absent id refuses before any confirm prompt, regardless of opt-in/yes.
    result = reground_bridge(path, step_ids=[9], allow_reground=True, yes=True)
    assert result.outcome == "step-missing"
    assert result.blocking == [9]
    assert path.read_text(encoding="utf-8") == before


def test_unsafe_when_named_step_parked(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT),
            _step(2, scope=StepScope.DEFERRED),
            _step(3),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(path, step_ids=[2], allow_reground=True, yes=True)
    assert result.outcome == "unsafe"
    assert result.blocking == [2]
    assert path.read_text(encoding="utf-8") == before


def test_noop_when_all_already_done(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.DONE), _step(2, status=StepStatus.CURRENT)]
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(path, step_ids=[1], allow_reground=True, yes=True)
    assert result.outcome == "noop"
    assert path.read_text(encoding="utf-8") == before


def test_noop_when_empty_ids(tmp_path):
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(path, step_ids=[], allow_reground=True, yes=True)
    assert result.outcome == "noop"
    assert path.read_text(encoding="utf-8") == before


def test_applied_flips_completed_on_disk(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.DONE), _step(2, status=StepStatus.CURRENT)]
    )
    path = _write_plan_file(tmp_path, plan)
    result = reground_bridge(path, step_ids=[2], allow_reground=True, yes=True)
    assert result.outcome == "applied"
    assert result.completed is True
    assert parse_plan(path).status is PlanStatus.COMPLETED


def test_bridge_preserves_ownership_when_plan_completes(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.DONE, concept_ids=[CONCEPT_A]),
            _step(2, status=StepStatus.CURRENT, concept_ids=[CONCEPT_B, CONCEPT_A]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)

    result = reground_bridge(path, step_ids=[2], allow_reground=True, yes=True)

    assert result.completed is True
    reparsed = parse_plan(path)
    assert [step.concept_ids for step in reparsed.steps] == [
        [CONCEPT_A],
        [CONCEPT_B, CONCEPT_A],
    ]


def test_recommended_reground_leaves_owned_plan_unchanged(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, concept_ids=[CONCEPT_B, CONCEPT_A]),
            _step(2, concept_ids=[CONCEPT_C]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")

    result = reground_bridge(path, step_ids=[1], allow_reground=False)

    assert result.outcome == "recommended"
    assert path.read_text(encoding="utf-8") == before
    assert parse_plan(path).step_by_id(1).concept_ids == [CONCEPT_B, CONCEPT_A]


def test_confirm_prompt_surfaces_flagged_ids_and_titles(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, files=["a.py"]),
            _step(2, files=["b.py"]),
            _step(3),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    captured = {}

    def _prompt(msg: str) -> str:
        captured["msg"] = msg
        return "n"

    reground_bridge(
        path, step_ids=[1, 2], allow_reground=True, yes=False, prompt_fn=_prompt
    )
    msg = captured["msg"]
    assert "1. Step 1" in msg and "2. Step 2" in msg
    assert "a.py" in msg and "b.py" in msg
    assert "built before re-baselining" in msg


def test_bridge_mints_no_recommendation():
    fields = {f for f in RegroundResult.__dataclass_fields__}
    assert not any("recommendation" in f.lower() for f in fields)
    for value in vars(reground).values():
        assert getattr(value, "__name__", "") != "Recommendation"


def test_bridge_never_routes_to_merge(tmp_path, monkeypatch):
    # No merge symbol is imported into the module...
    assert not hasattr(reground, "merge_steps")
    assert not hasattr(reground, "merge_bridge")
    source = Path(reground.__file__).read_text(encoding="utf-8")
    # No call to the merge executor (a docstring may name detail.merge_steps for
    # contrast); the runtime monkeypatch below is the authoritative no-routing check.
    assert "merge_steps(" not in source
    # ...and the apply path never reaches a merge primitive.
    import plan_tool.detail as detail

    def _boom(*_a, **_k):
        raise AssertionError("reground must not route to merge_steps")

    monkeypatch.setattr(detail, "merge_steps", _boom)
    path = _built_plan_file(tmp_path)
    result = reground_bridge(path, step_ids=[1, 2], allow_reground=True, yes=True)
    assert result.outcome == "applied"


def test_default_path_spends_no_claude():
    # No invoker= seam on the bridge (the autouse conftest gate enforces no
    # backend spawns on any path).
    params = inspect.signature(reground_bridge).parameters
    assert "invoker" not in params
    assert "claude_invoker" not in params


def test_imports_neither_launcher_nor_detail_at_module_level():
    source = Path(reground.__file__).read_text(encoding="utf-8")
    assert "import plan_tool.launcher" not in source
    assert "from plan_tool.launcher" not in source
    assert "import plan_tool.detail" not in source
    assert "from plan_tool.detail" not in source
    assert "import plan_tool.create" not in source
    assert "from plan_tool.create" not in source


def test_reground_still_imports_no_detail_or_launcher():
    # The whole-file grep catches only detail/launcher; a scope_out import (which
    # would transitively re-add the detail edge but not the literal substring) is
    # a separate constraint the renderer must uphold — assert it too.
    source = Path(reground.__file__).read_text(encoding="utf-8")
    assert "import plan_tool.detail" not in source
    assert "from plan_tool.detail" not in source
    assert "import plan_tool.launcher" not in source
    assert "from plan_tool.launcher" not in source
    assert "import plan_tool.scope_out" not in source
    assert "from plan_tool.scope_out" not in source
    assert "import plan_tool.create" not in source
    assert "from plan_tool.create" not in source


# --------------------------------------------------------------------------
# Bridge: re-baseline disposition (seed-first, then mark-done).
# --------------------------------------------------------------------------


def test_default_disposition_is_mark_done(tmp_path):
    path = _built_plan_file(tmp_path)
    result = reground_bridge(path, step_ids=[1, 2], allow_reground=True, yes=True)
    assert result.outcome == "applied"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()


def test_rebaseline_writes_seed_first_then_marks_done(tmp_path, monkeypatch):
    path = _built_plan_file(tmp_path)
    seed_dir = tmp_path / "docs" / "implementation-plans" / "plan-seeds"
    events: list[str] = []
    original_mark_steps_done = reground.mark_steps_done
    original_write_plan = reground.write_plan

    def observed_mark_steps_done(plan, step_ids):
        assert list(seed_dir.glob("*.md"))
        events.append("mark")
        return original_mark_steps_done(plan, step_ids)

    def observed_write_plan(plan_path, plan):
        assert list(seed_dir.glob("*.md"))
        events.append("write")
        return original_write_plan(plan_path, plan)

    monkeypatch.setattr(reground, "mark_steps_done", observed_mark_steps_done)
    monkeypatch.setattr(reground, "write_plan", observed_write_plan)

    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "applied"
    assert result.seed_path is not None and result.seed_path.is_file()
    assert result.seed_path.parent == tmp_path / "docs" / "implementation-plans" / "plan-seeds"
    assert events == ["mark", "write"]
    reparsed = parse_plan(path)
    assert reparsed.step_by_id(1).status is StepStatus.DONE
    assert reparsed.step_by_id(2).status is StepStatus.DONE


def test_rebaseline_seed_is_create_from_existing_consumable(tmp_path):
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    body = result.seed_path.read_text(encoding="utf-8")
    assert "plan-tool create --from-existing" in body
    assert "plan-tool reground rebaseline-seed" in body
    assert body.count("## References") == 1
    references = body.split("## References", maxsplit=1)[1].split(
        "## Provenance", maxsplit=1
    )[0]
    assert references.strip() == f"- Source plan: `{path}`"
    validate_from_existing_seed(body)


def test_rebaseline_seed_preserves_source_references(tmp_path):
    path = _built_plan_file(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Plan prose body that survives re-grounding.",
            "## References\n\n- [API](https://example.test/api)",
        ),
        encoding="utf-8",
    )

    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )

    body = result.seed_path.read_text(encoding="utf-8")
    references = body.split("## References", maxsplit=1)[1].split(
        "## Provenance", maxsplit=1
    )[0]
    assert references.strip() == "- [API](https://example.test/api)"


def test_rebaseline_seed_lists_flagged_steps_as_done_context(tmp_path):
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    body = result.seed_path.read_text(encoding="utf-8")
    done_context = body.split("## Done-context")[1].split("## Scope to re-plan")[0]
    assert "step 1: Step 1" in done_context
    assert "step 2: Step 2" in done_context


def test_rebaseline_seed_carries_flagged_step_concept_ids(tmp_path):
    plan = _plan(
        [
            _step(
                1,
                status=StepStatus.CURRENT,
                concept_ids=[CONCEPT_B, CONCEPT_A],
            ),
            _step(2, concept_ids=[CONCEPT_C]),
            _step(3),
        ]
    )

    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1, 2], source_path=tmp_path / "2-reground.md"
    )

    done_context = seed.split("## Done-context")[1].split("## Scope to re-plan")[0]
    assert "step 1: Step 1" in done_context
    assert f"concept_ids: [{CONCEPT_B}, {CONCEPT_A}]" in done_context
    assert "step 2: Step 2" in done_context
    assert f"concept_ids: [{CONCEPT_C}]" in done_context


def test_rebaseline_subset_seed_carries_remaining_scope(tmp_path):
    # Re-baseline a strict subset ([1,2]) — the not-flagged, not-done committed
    # step 3 must land in the scope-to-re-plan section so unbuilt scope survives.
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    body = result.seed_path.read_text(encoding="utf-8")
    scope = body.split("## Scope to re-plan")[1]
    assert "step 3: Step 3" in scope


def test_rebaseline_seed_carries_remaining_step_concept_ids(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, concept_ids=[CONCEPT_A]),
            _step(2, concept_ids=[CONCEPT_C, CONCEPT_B]),
        ]
    )

    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )

    scope = seed.split("## Scope to re-plan")[1]
    assert "step 2: Step 2" in scope
    assert f"concept_ids: [{CONCEPT_C}, {CONCEPT_B}]" in scope


def test_rebaseline_recommended_when_not_allowed(tmp_path):
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=False,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "recommended"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()
    assert path.read_text(encoding="utf-8") == before


def test_rebaseline_recommended_when_confirm_declined(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    path = _built_plan_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=False,
        prompt_fn=lambda _msg: "n",
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "recommended"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()
    assert path.read_text(encoding="utf-8") == before


def test_rebaseline_recommended_when_non_tty_without_yes(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=False,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "recommended"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()


def test_rebaseline_requires_repo_root(tmp_path):
    path = _built_plan_file(tmp_path)
    with pytest.raises(ValueError):
        reground_bridge(
            path,
            step_ids=[1, 2],
            allow_reground=True,
            yes=True,
            disposition="re-baseline",
            repo_root=None,
        )


def test_unknown_disposition_raises(tmp_path):
    path = _built_plan_file(tmp_path)
    with pytest.raises(ValueError):
        reground_bridge(
            path,
            step_ids=[1, 2],
            allow_reground=True,
            yes=True,
            disposition="bogus",
        )


def test_rebaseline_seed_never_overwrites(tmp_path):
    path = _built_plan_file(tmp_path)
    first = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    first_body = first.seed_path.read_text(encoding="utf-8")
    # Re-run on the same (now partly-done) plan — steps 1,2 already done, so mark
    # a fresh set; the second seed must not clobber the first.
    second = reground_bridge(
        path,
        step_ids=[3],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert second.seed_path != first.seed_path
    assert first.seed_path.read_text(encoding="utf-8") == first_body


def test_rebaseline_seed_collision_suffixes(tmp_path):
    # Two re-baselines of the *same* id set collide on the base stem; the second
    # gets a -2 suffix rather than overwriting.
    seeds = tmp_path / "docs" / "implementation-plans" / "plan-seeds"
    seeds.mkdir(parents=True)
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT),
            _step(2),
            _step(3),
            _step(4),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    from plan_tool import locator

    slug = locator.slug_from_filename(path)
    # Pre-seed the base path so the bridge must suffix.
    base = seeds / f"{slug}-reground-1-2.md"
    base.write_text("pre-existing seed", encoding="utf-8")
    result = reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.seed_path == seeds / f"{slug}-reground-1-2-2.md"
    assert base.read_text(encoding="utf-8") == "pre-existing seed"


def test_rebaseline_step_missing_writes_no_seed(tmp_path):
    path = _built_plan_file(tmp_path)
    result = reground_bridge(
        path,
        step_ids=[9],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "step-missing"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()


def test_rebaseline_unsafe_writes_no_seed(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT),
            _step(2, scope=StepScope.DEFERRED),
            _step(3),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    result = reground_bridge(
        path,
        step_ids=[2],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "unsafe"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()


def test_rebaseline_noop_writes_no_seed(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.DONE), _step(2, status=StepStatus.CURRENT)]
    )
    path = _write_plan_file(tmp_path, plan)
    result = reground_bridge(
        path,
        step_ids=[1],
        allow_reground=True,
        yes=True,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert result.outcome == "noop"
    assert result.seed_path is None
    assert not (tmp_path / "docs" / "implementation-plans" / "plan-seeds").exists()


def test_rebaseline_renderer_touches_no_disk(tmp_path):
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2), _step(3)])
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1, 2], source_path=tmp_path / "2-reground.md"
    )
    assert "plan-tool create --from-existing" in seed
    # Pure builder — nothing written anywhere.
    assert list(tmp_path.iterdir()) == []


def test_rebaseline_seed_carries_deferred_scope(tmp_path):
    # A not-done deferred step (parked behind a gate) must survive the re-baseline
    # in its own section — not be dropped, and not be promoted into re-plan scope.
    plan = _plan(
        [
            _step(1, status=StepStatus.DONE),
            _step(2, status=StepStatus.DONE),
            _step(3),  # committed, not done -> scope to re-plan
            _step(4, scope=StepScope.DEFERRED),  # parked -> deferred block
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1, 2], source_path=tmp_path / "2-reground.md"
    )
    deferred = seed.split("## Deferred (parked)")[1]
    assert "step 4: Step 4" in deferred
    # The deferred step is not silently folded into the re-plan scope.
    scope = seed.split("## Scope to re-plan")[1].split("## Deferred (parked)")[0]
    assert "step 3: Step 3" in scope
    assert "step 4: Step 4" not in scope


def test_rebaseline_seed_carries_deferred_step_concept_ids(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.DONE),
            _step(2, concept_ids=[CONCEPT_A]),
            _step(
                3,
                scope=StepScope.DEFERRED,
                concept_ids=[CONCEPT_B, CONCEPT_C],
            ),
        ]
    )

    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )

    deferred = seed.split("## Deferred (parked)")[1]
    assert "step 3: Step 3" in deferred
    assert f"concept_ids: [{CONCEPT_B}, {CONCEPT_C}]" in deferred


def test_rebaseline_seed_does_not_union_concept_ids(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, concept_ids=[CONCEPT_A]),
            _step(2, concept_ids=[CONCEPT_A, CONCEPT_B]),
            _step(3, concept_ids=[CONCEPT_C]),
        ]
    )

    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )

    step_lines = [line for line in seed.splitlines() if line.startswith("- step ")]
    assert step_lines == [
        f"- step 1: Step 1 [no files] (unspecified) — concept_ids: [{CONCEPT_A}]",
        (
            f"- step 2: Step 2 [no files] (unspecified) — concept_ids: "
            f"[{CONCEPT_A}, {CONCEPT_B}]"
        ),
        f"- step 3: Step 3 [no files] (unspecified) — concept_ids: [{CONCEPT_C}]",
    ]


def test_rebaseline_seed_carries_flagged_step_intents(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="flagged-one"),
            _step(2, intent="flagged-two"),
            _step(3, intent="remaining"),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1, 2], source_path=tmp_path / "2-reground.md"
    )
    done = seed.split("## Done-context", 1)[1].split("## Scope to re-plan", 1)[0]
    assert "intent: flagged-one" in done
    assert "intent: flagged-two" in done
    assert "remaining" not in done


def test_rebaseline_seed_carries_remaining_step_intents(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="done-why"),
            _step(2, intent="still-to-build"),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    scope = seed.split("## Scope to re-plan", 1)[1]
    assert "intent: still-to-build" in scope
    assert "done-why" not in scope


def test_rebaseline_seed_carries_deferred_step_intents(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="flagged"),
            _step(2, intent="remaining"),
            _step(3, scope=StepScope.DEFERRED, intent="parked-why"),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    deferred = seed.split("## Deferred (parked)", 1)[1]
    assert "intent: parked-why" in deferred
    assert "flagged" not in deferred
    assert "remaining" not in deferred


def test_rebaseline_seed_does_not_union_intents(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="alpha"),
            _step(2, intent="beta"),
            _step(3, intent="gamma"),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    step_lines = [line for line in seed.splitlines() if line.startswith("- step ")]
    assert step_lines == [
        "- step 1: Step 1 [no files] (unspecified) — intent: alpha",
        "- step 2: Step 2 [no files] (unspecified) — intent: beta",
        "- step 3: Step 3 [no files] (unspecified) — intent: gamma",
    ]


def test_rebaseline_seed_omits_absent_step_intent(tmp_path):
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2, intent="has-why")])
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    step_lines = [line for line in seed.splitlines() if line.startswith("- step ")]
    assert "intent:" not in step_lines[0]
    assert "intent: has-why" in step_lines[1]


def test_rebaseline_seed_omits_blank_step_intent(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent="  \n "),
            _step(2, intent="real"),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    done = seed.split("## Done-context", 1)[1].split("## Scope to re-plan", 1)[0]
    assert "intent:" not in done


@pytest.mark.parametrize("placeholder", ["TODO", "_(TODO)_"])
def test_rebaseline_seed_omits_placeholder_intents(placeholder, tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT, intent=placeholder),
            _step(2, intent=placeholder),
        ],
        intent=placeholder,
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "Source plan intent:" not in seed
    assert " — intent:" not in seed


def test_rebaseline_seed_omits_a_tbd_intent(tmp_path):
    # A ``TBD`` intent states no why; rendering it into the re-baseline seed
    # would hand the re-decomposition a placeholder as its stated purpose.
    plan = _plan(
        [_step(1, status=StepStatus.CURRENT, intent="TBD"), _step(2, intent="TBD")],
        intent="TBD",
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "Source plan intent:" not in seed
    assert "intent: TBD" not in seed


def test_rebaseline_step_intent_collapses_to_one_line(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.CURRENT, intent="one\ntwo"), _step(2)]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    line = next(ln for ln in seed.splitlines() if ln.startswith("- step 1:"))
    assert "\n" not in line
    assert "intent: one two" in line


def test_rebaseline_bullet_suffix_order_is_stable(tmp_path):
    # Docstring contract: intent first, then concept_ids.
    plan = _plan(
        [
            _step(
                1,
                status=StepStatus.CURRENT,
                intent="why",
                concept_ids=[CONCEPT_A],
            ),
            _step(2),
        ]
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    line = next(ln for ln in seed.splitlines() if ln.startswith("- step 1:"))
    assert line == (
        f"- step 1: Step 1 [no files] (unspecified) — intent: why "
        f"— concept_ids: [{CONCEPT_A}]"
    )


def test_rebaseline_seed_names_the_source_plan_intent(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.CURRENT), _step(2)],
        intent="whole-plan why",
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert seed.count("Source plan intent: whole-plan why") == 1
    assert "still serves that purpose" in seed


def test_rebaseline_seed_omits_source_plan_intent_when_absent(tmp_path):
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2)])
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "Source plan intent:" not in seed


def test_rebaseline_seed_writes_no_outcome_heading(tmp_path):
    plan = _plan(
        [_step(1, status=StepStatus.CURRENT, intent="s"), _step(2)],
        intent="p",
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "## Outcome" not in seed
    params = inspect.signature(render_rebaseline_seed).parameters
    assert "plan_intent" not in params


def test_rebaseline_no_intent_anywhere_renders_no_intent_line(tmp_path):
    plan = _plan([_step(1, status=StepStatus.CURRENT), _step(2)])
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "Source plan intent:" not in seed
    assert " — intent:" not in seed


def test_rebaseline_seed_omits_empty_concept_ownership(tmp_path):
    plan = _plan(
        [
            _step(1, status=StepStatus.CURRENT),
            _step(2, concept_ids=[CONCEPT_A]),
        ]
    )

    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )

    step_lines = [line for line in seed.splitlines() if line.startswith("- step ")]
    assert step_lines[0] == "- step 1: Step 1 [no files] (unspecified)"
    assert "concept_ids" not in step_lines[0]
    assert f"concept_ids: [{CONCEPT_A}]" in step_lines[1]


def test_rebaseline_seed_omits_deferred_block_when_none(tmp_path):
    # All-committed plan carries no parked scope, so the block is elided entirely.
    plan = _plan([_step(1, status=StepStatus.DONE), _step(2)])
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1], source_path=tmp_path / "2-reground.md"
    )
    assert "## Deferred (parked)" not in seed


def test_rebaseline_confirm_prompt_mentions_seed(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    path = _built_plan_file(tmp_path)
    captured = {}

    def _prompt(msg: str) -> str:
        captured["msg"] = msg
        return "n"

    reground_bridge(
        path,
        step_ids=[1, 2],
        allow_reground=True,
        yes=False,
        prompt_fn=_prompt,
        disposition="re-baseline",
        repo_root=tmp_path,
    )
    assert "create --from-existing" in captured["msg"]
