"""Unit tests for the intent proposer: prompt, response parse, the operator
walk, the pure plan transform, and the apply-or-recommend bridge.

Never spawns a real backend or blocks on stdin — the ``invoker`` and
``input_fn`` seams are injected fakes.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Callable

import pytest
import yaml

import plan_tool.intent_proposal as intent_proposal
from plan_tool.intent_proposal import (
    IntentDraft,
    apply_intent_drafts,
    parse_intent_drafts,
    propose_intents,
    render_intent_prompt,
    review_intent_drafts,
)
from plan_tool.parser import _coerce_enums, parse_plan
from plan_tool.schema import (
    ChangeType,
    Complexity,
    Plan,
    PlanStatus,
    Priority,
    Step,
)


def _step(
    id: int,
    *,
    title: str | None = None,
    intent: str | None = None,
    files: list[str] | None = None,
    change_type: ChangeType | None = None,
    complexity: Complexity | None = None,
    depends_on: list[int] | None = None,
) -> Step:
    return Step(
        id=id,
        title=title or f"Step {id}",
        intent=intent,
        files=files or [],
        change_type=change_type,
        complexity=complexity,
        depends_on=depends_on or [],
    )


def _plan(*steps: Step, intent: str | None = None) -> Plan:
    return Plan(
        title="Intent demo",
        intent=intent,
        status=PlanStatus.IN_PROGRESS,
        priority=Priority.MEDIUM,
        steps=list(steps),
    )


def _write_plan_file(tmp_path: Path, plan: Plan, name: str = "2-intent.md") -> Path:
    dumped = _coerce_enums(plan.model_dump(exclude_defaults=True, exclude_none=True))
    fm = yaml.safe_dump(
        dumped, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    path = tmp_path / name
    path.write_text(
        f"---\n{fm}---\n\n# Intent demo\n\nProse body that survives the write.\n",
        encoding="utf-8",
    )
    return path


def _queue_input(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def fake(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:  # pragma: no cover - guards a test bug
            raise AssertionError(f"input ran out at: {prompt!r}") from exc

    return fake


def _raises_if_called(prompt: str) -> str:  # invoker that must not run
    raise AssertionError("invoker should not be called")


def _canned(payload: object) -> Callable[[str], str]:
    def fake(prompt: str) -> str:
        return json.dumps(payload)

    return fake


def _counting(payload: object) -> tuple[Callable[[str], str], list[str]]:
    calls: list[str] = []

    def fake(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(payload)

    return fake, calls


# --------------------------------------------------------------------------
# Prompt.
# --------------------------------------------------------------------------


def test_prompt_names_every_requested_step_id():
    plan = _plan(_step(1), _step(2, title="Wire the walk"), _step(3))
    prompt = render_intent_prompt(plan, plan_needs_intent=False, step_ids=[1, 3])
    assert "- 1 — Step 1" in prompt
    assert "- 3 — Step 3" in prompt


def test_prompt_omits_the_plan_arm_when_the_plan_intent_is_present():
    plan = _plan(_step(1), intent="ship the field end to end")
    with_plan = render_intent_prompt(plan, plan_needs_intent=True, step_ids=[1])
    without_plan = render_intent_prompt(plan, plan_needs_intent=False, step_ids=[1])
    assert '- "plan" — the plan itself' in with_plan
    assert '- "plan" — the plan itself' not in without_plan


def test_prompt_carries_the_callers_source_text():
    plan = _plan(_step(1))
    prompt = render_intent_prompt(
        plan,
        plan_needs_intent=True,
        step_ids=[1],
        source_text="## Outcome\n\nEvery plan carries a stated why.",
    )
    assert "Every plan carries a stated why." in prompt


def test_prompt_never_quotes_an_existing_intent():
    plan = _plan(
        _step(1, intent="a perfectly good reason already written"),
        _step(2),
    )
    prompt = render_intent_prompt(plan, plan_needs_intent=False, step_ids=[2])
    assert "a perfectly good reason already written" not in prompt
    assert "- 1 —" not in prompt


def test_prompt_grounds_a_target_in_its_files_and_classification():
    plan = _plan(
        _step(
            1,
            files=["plan_tool/review.py"],
            change_type=ChangeType.REFACTOR,
            complexity=Complexity.LOW,
            depends_on=[],
        ),
        _step(2, depends_on=[1]),
    )
    prompt = render_intent_prompt(plan, plan_needs_intent=False, step_ids=[1, 2])
    assert "files: plan_tool/review.py" in prompt
    assert "change_type: refactor" in prompt
    assert "complexity: low" in prompt
    assert "depends_on: 1" in prompt


# --------------------------------------------------------------------------
# Response parse.
# --------------------------------------------------------------------------


def test_unparseable_response_returns_none():
    assert (
        parse_intent_drafts(
            "I could not think of one, sorry.",
            plan_needs_intent=True,
            valid_step_ids={1},
        )
        is None
    )


def test_empty_array_parses_as_no_drafts():
    assert (
        parse_intent_drafts("[]", plan_needs_intent=True, valid_step_ids={1}) == []
    )


def test_malformed_entry_is_dropped_not_fatal():
    raw = json.dumps(
        ["not an object", {"target": 1, "intent": "keep the loop honest"}]
    )
    drafts = parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1})
    assert drafts == [IntentDraft(step_id=1, text="keep the loop honest")]


def test_draft_for_an_unknown_step_id_is_dropped():
    raw = json.dumps([{"target": 9, "intent": "why step nine exists"}])
    assert parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1}) == []


def test_quoted_numeral_target_is_coerced():
    raw = json.dumps([{"target": "1", "intent": "why step one exists"}])
    assert parse_intent_drafts(
        raw, plan_needs_intent=False, valid_step_ids={1}
    ) == [IntentDraft(step_id=1, text="why step one exists")]


@pytest.mark.parametrize(
    "raw_target",
    [
        "--5",
        "²",
        "5.0",
        "2_0",
        "٢",
        "02",
        "0",
        pytest.param("1" + "0" * 4999, id="oversized"),
    ],
)
def test_malformed_numeral_target_is_dropped_without_raising(raw_target: str):
    raw = json.dumps([{"target": raw_target, "intent": "why step one exists"}])
    assert parse_intent_drafts(
        raw, plan_needs_intent=False, valid_step_ids={1}
    ) == []


def test_draft_for_a_step_not_requested_is_dropped():
    raw = json.dumps(
        [
            {"target": 1, "intent": "why step one exists"},
            {"target": 2, "intent": "step two already has one"},
        ]
    )
    drafts = parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1})
    assert [d.step_id for d in drafts] == [1]


def test_placeholder_draft_is_dropped():
    raw = json.dumps([{"target": 1, "intent": "_(TODO)_"}])
    assert parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1}) == []


def test_plan_target_maps_to_the_plan_level_draft():
    raw = json.dumps([{"target": "plan", "intent": "why this plan exists"}])
    drafts = parse_intent_drafts(raw, plan_needs_intent=True, valid_step_ids=set())
    assert drafts == [IntentDraft(step_id=None, text="why this plan exists")]


def test_plan_draft_is_dropped_when_the_plan_arm_was_not_requested():
    raw = json.dumps([{"target": "plan", "intent": "why this plan exists"}])
    assert parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1}) == []


def test_second_draft_for_a_target_is_dropped():
    raw = json.dumps(
        [
            {"target": 1, "intent": "the first reason"},
            {"target": 1, "intent": "a second, competing reason"},
        ]
    )
    drafts = parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1})
    assert drafts == [IntentDraft(step_id=1, text="the first reason")]


def test_trailing_prose_after_the_array_is_tolerated():
    raw = '[{"target": 1, "intent": "why one exists"}]\n\nHope that helps!'
    drafts = parse_intent_drafts(raw, plan_needs_intent=False, valid_step_ids={1})
    assert [d.text for d in drafts] == ["why one exists"]


# --------------------------------------------------------------------------
# propose_intents: the single round-trip.
# --------------------------------------------------------------------------


def test_propose_makes_one_call_for_the_whole_plan():
    plan = _plan(_step(1), _step(2), _step(3))
    invoker, calls = _counting(
        [
            {"target": "plan", "intent": "why the plan exists"},
            {"target": 1, "intent": "why one exists"},
            {"target": 3, "intent": "why three exists"},
        ]
    )
    drafts = propose_intents(
        plan, invoker=invoker, plan_needs_intent=True, step_ids=[1, 3]
    )
    assert len(calls) == 1
    assert [d.step_id for d in drafts] == [None, 1, 3]


def test_propose_makes_no_call_with_nothing_to_ask_about():
    plan = _plan(_step(1))
    assert (
        propose_intents(
            plan, invoker=_raises_if_called, plan_needs_intent=False, step_ids=[]
        )
        == []
    )


def test_propose_returns_none_on_an_unparseable_response():
    plan = _plan(_step(1))
    assert (
        propose_intents(
            plan,
            invoker=lambda prompt: "no JSON here",
            plan_needs_intent=False,
            step_ids=[1],
        )
        is None
    )


def test_invoker_has_no_default():
    for fn in (propose_intents,):
        param = inspect.signature(fn).parameters["invoker"]
        assert param.default is inspect.Parameter.empty, fn.__name__


# --------------------------------------------------------------------------
# Operator walk: accept / edit / decline.
# --------------------------------------------------------------------------


def test_accept_keeps_the_drafted_text():
    draft = IntentDraft(step_id=1, text="why one exists")
    assert review_intent_drafts([draft], input_fn=_queue_input(["a"])) == [draft]


def test_enter_defaults_to_accept():
    draft = IntentDraft(step_id=None, text="why the plan exists")
    assert review_intent_drafts([draft], input_fn=_queue_input([""])) == [draft]


def test_edit_replaces_the_text():
    draft = IntentDraft(step_id=1, text="a draft the operator dislikes")
    kept = review_intent_drafts(
        [draft], input_fn=_queue_input(["e", "the reason I actually meant"])
    )
    assert kept == [IntentDraft(step_id=1, text="the reason I actually meant")]


def test_blank_edit_is_a_decline():
    draft = IntentDraft(step_id=1, text="a draft the operator dislikes")
    assert review_intent_drafts([draft], input_fn=_queue_input(["e", "   "])) == []


def test_placeholder_edit_is_a_decline():
    draft = IntentDraft(step_id=1, text="a draft the operator dislikes")
    assert review_intent_drafts([draft], input_fn=_queue_input(["e", "TODO"])) == []


def test_decline_drops_the_draft():
    draft = IntentDraft(step_id=1, text="why one exists")
    assert review_intent_drafts([draft], input_fn=_queue_input(["d"])) == []


def test_unrecognized_key_re_prompts():
    draft = IntentDraft(step_id=1, text="why one exists")
    assert review_intent_drafts([draft], input_fn=_queue_input(["x", "a"])) == [draft]


def test_walk_resolves_each_draft_independently():
    drafts = [
        IntentDraft(step_id=None, text="why the plan exists"),
        IntentDraft(step_id=1, text="why one exists"),
        IntentDraft(step_id=2, text="why two exists"),
    ]
    kept = review_intent_drafts(drafts, input_fn=_queue_input(["a", "d", ""]))
    assert [d.step_id for d in kept] == [None, 2]


def test_interrupted_walk_declines_the_remaining_drafts():
    def boom(prompt: str) -> str:
        raise EOFError

    drafts = [IntentDraft(step_id=1, text="why one exists")]
    assert review_intent_drafts(drafts, input_fn=boom) == []


# --------------------------------------------------------------------------
# Pure transform.
# --------------------------------------------------------------------------


def test_apply_sets_the_plan_and_step_intents():
    plan = _plan(_step(1), _step(2))
    updated = apply_intent_drafts(
        plan,
        [
            IntentDraft(step_id=None, text="why the plan exists"),
            IntentDraft(step_id=2, text="why two exists"),
        ],
    )
    assert updated.intent == "why the plan exists"
    assert updated.step_by_id(2).intent == "why two exists"


def test_apply_leaves_untargeted_steps_unchanged():
    plan = _plan(_step(1, intent="already stated"), _step(2))
    updated = apply_intent_drafts(plan, [IntentDraft(step_id=2, text="why two")])
    assert updated.step_by_id(1).intent == "already stated"
    assert updated.intent is None


def test_apply_collapses_whitespace_to_one_line():
    plan = _plan(_step(1))
    updated = apply_intent_drafts(
        plan, [IntentDraft(step_id=1, text="why one\n\n## Not a heading   exists")]
    )
    assert updated.step_by_id(1).intent == "why one ## Not a heading exists"


def test_apply_returns_a_copy():
    plan = _plan(_step(1))
    updated = apply_intent_drafts(
        plan,
        [
            IntentDraft(step_id=None, text="why the plan exists"),
            IntentDraft(step_id=1, text="why one exists"),
        ],
    )
    assert updated is not plan
    assert plan.intent is None
    assert plan.step_by_id(1).intent is None


# --------------------------------------------------------------------------
# Module-level contracts.
# --------------------------------------------------------------------------


def test_module_imports_no_cli_package():
    source = Path(intent_proposal.__file__).read_text(encoding="utf-8")
    assert "plan_tool.cli" not in source


def test_module_defines_no_second_presence_check():
    """``review.is_usable_intent`` is the only judge of a draft."""
    names = [n for n in vars(intent_proposal) if "usable" in n or "placeholder" in n]
    assert names == ["is_usable_intent"]


def test_module_mints_no_recommendation():
    source = Path(intent_proposal.__file__).read_text(encoding="utf-8")
    assert "Recommendation" not in source


# --------------------------------------------------------------------------
# Regressions from the xhigh review.
# --------------------------------------------------------------------------


def test_trailing_prose_containing_a_bracket_still_parses():
    """The prompt promises trailing prose is tolerated, so a `]` in it must not
    swallow the array — `rfind` did, turning a good response into `None`."""
    raw = (
        '[{"target": "plan", "intent": "a why"}]\n\n'
        "I proposed nothing for step 2 [not enough grounding]."
    )
    drafts = parse_intent_drafts(
        raw, plan_needs_intent=True, valid_step_ids=set()
    )
    assert drafts is not None
    assert [d.text for d in drafts] == ["a why"]


def test_bracket_inside_a_draft_string_does_not_end_the_scan():
    raw = '[{"target": "plan", "intent": "ship the [beta] flag"}]'
    drafts = parse_intent_drafts(
        raw, plan_needs_intent=True, valid_step_ids=set()
    )
    assert drafts is not None
    assert drafts[0].text == "ship the [beta] flag"


def test_response_with_no_array_is_still_unparseable():
    assert (
        parse_intent_drafts(
            "I could not ground any of these.",
            plan_needs_intent=True,
            valid_step_ids=set(),
        )
        is None
    )


def test_keyboard_interrupt_aborts_rather_than_declining_the_rest():
    """Ctrl-C means stop the run, not "accept what I have". Conflating it with
    EOFError made `plan-tool create` uninterruptible at this gate."""
    drafts = [IntentDraft(step_id=None, text="a why")]

    def boom(_prompt: str) -> str:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        review_intent_drafts(drafts, input_fn=boom)


def test_eof_still_declines_the_remaining_drafts():
    drafts = [IntentDraft(step_id=None, text="a why")]

    def eof(_prompt: str) -> str:
        raise EOFError

    assert review_intent_drafts(drafts, input_fn=eof) == []
