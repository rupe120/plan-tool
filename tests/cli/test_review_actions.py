"""Characterization tests for the ``_build_review_action_fn`` action matrix.

``_build_review_action_fn`` returns the ``action(rec)`` callable the review
walk invokes when the user applies a recommendation. ``action`` is a routing
table: it inspects each recommendation and dispatches to one of five
branches, returning a short status string the walk records. These tests pin
the *fall-through* rows of that table — the two terminal branches that
resolve deterministically without spawning a Claude call — so the upcoming
"split cli.py into an intent-grouped package" refactor can relocate the
builder without changing what an un-dispatchable recommendation reports back.

The claude-dispatching rows of the matrix are already pinned DIRECTLY in
``tests/test_review_walk.py`` (verdict ``directly covered`` in
``COVERAGE_BASELINE.md``); per the cli-package-split plan's no-duplication
rule, the inventory pointer stands in for a new test rather than copying the
mechanics here:

  | recommendation shape                       | branch              | pinned by (test_review_walk.py)            |
  |--------------------------------------------|---------------------|--------------------------------------------|
  | ``run --mode reconcile`` suggested action  | _dispatch_reconcile | TestNestedReconcileWalk (reconcile + reuse)|
  | ``detail --reconcile`` suggested action    | _dispatch_detail_reconcile | TestRecognizedActionParser (descriptor) |
  | ``detail --step N [--force]`` action       | _dispatch_detail    | test_action_fn_dispatches_detail[_force]   |
  | reconcile/claude-source finding            | _dispatch_apply_finding | test_action_fn_dispatches_apply_finding_*  |
  | MISSING_PARENT file-check finding          | _dispatch_file_check_create | TestFileCheckCreateDispatch          |
  | apply-skip downgrade on file-check ``fix``  | (walk annotation)  | TestApplySkipDowngradesAnnotation          |
  | free-form unrecognized suggested action    | (terminal)          | test_action_fn_with_unrecognized_suggestion|

The two terminal rows below need no domain stubbing — they exercise only
``recognized_action`` / ``should_apply_as_finding`` /
``file_check_create_target`` (pure predicates) and the final ``if`` ladder —
so they are pinned here as the consolidated, byte-exact wording of the
matrix's no-op responses.

Split-proof conventions (see ``test_package_surface.py``): the builder is
imported from ``plan_tool.cli`` and called with a directly-constructed
``PlanToolContext``; no ``plan_tool.cli`` module global is patched. The
terminal branches never dereference ``plan_path`` / ``ctx``, so a bare repo
root suffices.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from plan_tool.cli import _build_review_action_fn
from plan_tool.locator import PlanToolContext
from plan_tool.review import Recommendation
from plan_tool.review_walk import WalkState
from plan_tool.schema import Plan


def _action_fn(tmp_path: Path):
    ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
    return _build_review_action_fn(
        ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
    )


def _assert_walk_state(
    state: WalkState,
    *,
    apply_skip: bool,
    halt_requested: bool = False,
    halt_apply_landed: bool = False,
    applied_ids: frozenset = frozenset(),
    apply_failed: bool = False,
) -> None:
    """Pin the full post-call ``WalkState`` tail step 2 consolidates.

    Checks the four kernel fields (``apply_skip`` + the halt pair +
    ``applied_structural_finding_ids``) plus ``apply_failed`` (which none of
    the four structural dispatchers touch — it belongs to the apply-error
    path) in one place, defaulting every field to its "untouched" value so a
    test only names the fields an outcome actually moves.
    """
    assert state.apply_skip is apply_skip
    assert state.halt_requested is halt_requested
    assert state.halt_apply_landed is halt_apply_landed
    assert state.applied_structural_finding_ids == set(applied_ids)
    assert state.apply_failed is apply_failed


class TestActionMatrixTerminalRows:
    """The two rows where ``action`` resolves without dispatching work."""

    def test_no_suggested_action_returns_noop_notice(
        self, tmp_path: Path
    ) -> None:
        # ``deps`` source is neither a recognized command nor in the
        # apply-as-finding set, and a None suggested_action isn't a
        # file-check path move — so the ladder falls to the no-action row.
        rec = Recommendation(
            id="step2-deps-1",
            source="deps",
            severity="high",
            step_id=2,
            title="blocked on step 1",
            body="step 2 depends on step 1 which is not done",
            suggested_action=None,
        )
        assert _action_fn(tmp_path)(rec) == (
            "no suggested action on this recommendation"
        )

    def test_unrecognized_suggestion_returns_manual_run_notice(
        self, tmp_path: Path
    ) -> None:
        # A free-form suggested_action that matches no command shape and
        # whose source doesn't apply-as-finding falls to the terminal
        # "run it manually" row.
        rec = Recommendation(
            id="step2-deps-2",
            source="deps",
            severity="high",
            step_id=2,
            title="blocked on step 1",
            body="unblock the dependency",
            suggested_action="unblock dependency on step 1",
        )
        assert _action_fn(tmp_path)(rec) == (
            "suggested action isn't a recognized reconcile or detail "
            "invocation; run it manually in another shell"
        )

    def test_data_contract_source_requires_command_local_action_callback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review_walk import is_dispatchable

        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("data-contract must not call apply_finding")

        monkeypatch.setattr("plan_tool.launcher.apply_finding", boom)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx,
            plan_path=tmp_path / "demo.md",
            plan_name="demo",
            extra_apply_sources=frozenset({"data-contract"}),
        )
        rec = Recommendation(
            id="contract-1",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="DATA_CONTRACT.md drift",
            body="DATA_CONTRACT.md is missing a field",
            suggested_action="Update DATA_CONTRACT.md",
        )

        assert is_dispatchable(
            rec, extra_apply_sources=frozenset({"data-contract"})
        ) is True
        assert action(rec) == (
            "suggested action isn't a recognized reconcile or detail "
            "invocation; run it manually in another shell"
        )

    def test_data_contract_source_without_opt_in_is_terminal_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review_walk import is_dispatchable

        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("data-contract must not call apply_finding")

        monkeypatch.setattr("plan_tool.launcher.apply_finding", boom)
        rec = Recommendation(
            id="contract-2",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="DATA_CONTRACT.md drift",
            body="DATA_CONTRACT.md is missing a field",
            suggested_action=None,
        )

        assert is_dispatchable(rec) is False
        assert _action_fn(tmp_path)(rec) == (
            "no suggested action on this recommendation"
        )


class TestOperatorFeedbackSteersApply:
    """The walk's ``(f)eedback`` choice stashes guidance on
    ``WalkState.pending_feedback``; the apply dispatcher must forward it
    to ``apply_finding`` and clear it so it never leaks onto a later rec."""

    def test_apply_finding_consumes_and_clears_operator_feedback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake_apply_finding(plan_path, **kwargs):
            captured.update(kwargs)
            # APPLIED + empty diff → dispatcher returns the no-op early,
            # before any keep/revert prompt, having already consumed
            # feedback and called apply_finding.
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="",
                summary="", pre_snapshot={}, introduced_findings=(),
                resolved_findings=(),
            )

        # The dispatcher binds ``apply_finding`` via a body-local import at
        # build time, so patch the launcher symbol BEFORE building.
        monkeypatch.setattr(
            "plan_tool.launcher.apply_finding", fake_apply_finding
        )

        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        state = WalkState()
        state.pending_feedback = "only edit the YAML; leave the prose alone"
        action = _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=state,
        )
        rec = Recommendation(
            id="gap-1",
            source="plan-completeness",
            severity="medium",
            step_id=3,
            title="conceptual gap",
            body="the plan leaves concept X uncovered",
            suggested_action="specify how step 3 covers concept X",
            confidence=None,
        )
        action(rec)

        # Forwarded to apply_finding as authoritative steering …
        assert captured["operator_feedback"] == (
            "only edit the YAML; leave the prose alone"
        )
        assert captured["finding_body"] == (
            "[MEDIUM] conceptual gap\n\nconfidence: unknown\n\n"
            "the plan leaves concept X uncovered"
        )
        # … and cleared so the next rec's apply starts clean.
        assert state.pending_feedback == ""


def _stub_blocked_structural(
    monkeypatch: pytest.MonkeyPatch, *, pre_snapshot=None, diff_text=""
):
    """Make ``apply_finding`` return a ``BLOCKED-STRUCTURAL`` verdict.

    Bound at build time via the builder's body-local
    ``from plan_tool.launcher import (...)`` block, so patch the launcher
    symbol BEFORE building the action fn.
    """
    snap = {} if pre_snapshot is None else pre_snapshot

    def fake(plan_path, **kwargs):
        return SimpleNamespace(
            exit_code=0, verdict="BLOCKED-STRUCTURAL", diff_text=diff_text,
            summary="step mixes refactor + feature", pre_snapshot=snap,
            introduced_findings=(), resolved_findings=(),
        )

    monkeypatch.setattr("plan_tool.launcher.apply_finding", fake)


def _stub_escalate(monkeypatch: pytest.MonkeyPatch, result):
    """Make ``escalate_to_split`` return ``result`` and record its kwargs.

    Bound at build time alongside ``apply_finding`` — patch before building.
    Returns the recording list so callers can assert call count / kwargs.
    """
    calls: list[dict] = []

    def fake(plan_path, **kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr("plan_tool.launcher.escalate_to_split", fake)
    return calls


def _escalate_result(outcome, *, target_id=4, recommendation=None, blocking=None):
    return SimpleNamespace(
        outcome=outcome, target_id=target_id,
        recommendation=recommendation, blocking=blocking or [],
    )


def _structural_rec(*, step_id=4, source="claude"):
    suffix = step_id if step_id is not None else "plan"
    return Recommendation(
        id=f"{source}-struct-{suffix}",
        source=source,
        severity="high",
        step_id=step_id,
        title="step mixes refactor + feature",
        body="split this step into a refactor half then a feature half",
        suggested_action=None,
    )


class TestStructuralEscalation:
    """A ``BLOCKED-STRUCTURAL`` apply verdict routes to
    ``escalate_to_split`` instead of the ``BLOCKED``/empty-diff arms."""

    def _build(self, tmp_path, monkeypatch, **kwargs):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            **kwargs,
        )

    def test_blocked_structural_reverts_before_escalating(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        order: list = []
        snap = {tmp_path / "demo.md": "partial edit"}
        _stub_blocked_structural(monkeypatch, pre_snapshot=snap)
        monkeypatch.setattr(
            "plan_tool.launcher._restore_text_files",
            lambda s: order.append(("revert", s)),
        )

        def fake_escalate(plan_path, **kwargs):
            order.append(("escalate", kwargs))
            return _escalate_result("applied")

        monkeypatch.setattr(
            "plan_tool.launcher.escalate_to_split", fake_escalate
        )

        action = self._build(tmp_path, monkeypatch)
        action(_structural_rec())

        assert order == [("revert", snap), ("escalate", order[1][1])]
        assert sum(1 for o in order if o[0] == "escalate") == 1

    def test_blocked_structural_routes_past_empty_diff_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch, diff_text="")
        _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 4 ..."
                ),
            ),
        )
        action = self._build(tmp_path, monkeypatch)
        result = action(_structural_rec())
        assert "didn't change" not in result
        assert "escalated structural finding" in result

    def test_escalation_applied_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied", target_id=4))
        action = self._build(tmp_path, monkeypatch)
        result = action(_structural_rec(step_id=4))
        assert "applied a 2-step split at step 4" in result

    def test_escalation_applied_refreshes_drift_baseline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.scope_guard import ReconcileScopeGuard, ScopeGuardBuffer

        # No drift on the pre-apply check, so the dispatcher reaches the arm.
        monkeypatch.setattr(
            "plan_tool.drift_detection.check_drift", lambda lock: []
        )
        refreshed: list = []
        monkeypatch.setattr(
            "plan_tool.drift_detection.refresh_snapshot",
            lambda lock: refreshed.append(lock),
        )
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied", target_id=7))

        lock = object()
        guard = ReconcileScopeGuard(
            scope_dirs=[], in_scope=set(), scope_buffer=ScopeGuardBuffer(),
            file_to_step={}, repo_root=tmp_path, iter_lock=lock,
        )
        action = self._build(
            tmp_path, monkeypatch, allow_split=True,
            reconcile_scope_guard=guard,
        )
        result = action(_structural_rec(step_id=7))
        assert "applied a 2-step split at step 7" in result
        assert refreshed == [lock]

    def test_escalation_recommended_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        calls = _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 4 --into ..."
                ),
            ),
        )
        action = self._build(tmp_path, monkeypatch)
        result = action(_structural_rec())
        assert "plan-tool split demo --step 4" in result
        assert len(calls) == 1

    def test_escalation_unsafe_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        # recommendation=None on unsafe; the arm must not dereference it.
        _stub_escalate(
            monkeypatch,
            _escalate_result("unsafe", blocking=[5, 6], recommendation=None),
        )
        action = self._build(tmp_path, monkeypatch)
        result = action(_structural_rec())
        assert "5" in result and "6" in result
        assert "not PENDING" in result

    def test_escalation_proposal_unusable_and_step_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("proposal-unusable"))
        action = self._build(tmp_path, monkeypatch)
        assert action(_structural_rec()) == (
            "structural escalation: split proposal unusable; left as-is"
        )

        _stub_escalate(monkeypatch, _escalate_result("step-missing"))
        action = self._build(tmp_path, monkeypatch)
        result = action(_structural_rec(step_id=9))
        assert "step 9 not found" in result

    def test_plan_level_verdict_not_escalated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        action = self._build(tmp_path, monkeypatch)
        # plan-level source carries step_id=None — no concrete step to split.
        result = action(_structural_rec(step_id=None, source="plan-completeness"))
        assert calls == []  # escalate_to_split never called
        assert "re-decompose through a session-directed edit" in result

    def test_escalation_passes_proposer_and_allow_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create

        _stub_blocked_structural(monkeypatch)
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        action = self._build(tmp_path, monkeypatch, allow_split=True)
        action(_structural_rec())
        assert calls[0]["invoker"] is create.shell_claude_invoker
        assert calls[0]["allow_split"] is True
        assert calls[0]["prompt_fn"] is None

    def test_escalation_yes_to_all_forces_recommend_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        calls = _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(suggested_action="plan-tool split"),
            ),
        )
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, monkeypatch, allow_split=True, state=state,
        )
        action(_structural_rec())
        # A blanket yes-to-all never auto-confirms a split.
        assert calls[0]["allow_split"] is False
        assert calls[0]["prompt_fn"] is None

    def test_reverted_disposition_suppresses_scope_and_drift(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.scope_guard import ReconcileScopeGuard, ScopeGuardBuffer

        # Pre-apply drift check sees no drift, so the arm is reached.
        monkeypatch.setattr(
            "plan_tool.drift_detection.check_drift", lambda lock: []
        )

        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("scope eval ran on a reverted disposition")

        monkeypatch.setattr("plan_tool.scope_guard.evaluate_apply_scope", boom)
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(suggested_action="plan-tool split"),
            ),
        )
        guard = ReconcileScopeGuard(
            scope_dirs=[], in_scope=set(), scope_buffer=ScopeGuardBuffer(),
            file_to_step={}, repo_root=tmp_path, iter_lock=object(),
        )
        action = self._build(
            tmp_path, monkeypatch, reconcile_scope_guard=guard,
        )
        # Must not raise — the finally scope/drift eval is gated on
        # phase_outcome == "success", which the "reverted" arm never sets.
        result = action(_structural_rec())
        assert "escalated structural finding" in result

    def test_allow_split_threads_into_detail_reconcile_subwalks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.review_actions as ra
        from plan_tool.cli import reconcile as rec_mod

        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, monkeypatch, allow_split=True, state=state,
        )

        # A saved detail-reconcile so the reuse path builds a sub-walk fn.
        monkeypatch.setattr(
            rec_mod, "_find_saved_detail_reconcile_for_step",
            lambda *a, **k: (
                Path("saved.json"),
                SimpleNamespace(recommendations=[_structural_rec()]),
            ),
        )
        monkeypatch.setattr(
            rec_mod, "_walk_with_reconcile_phase", lambda *a, **k: None
        )

        # Spy the builder so the recursive sub-walk build records its kwargs.
        captured: list[dict] = []

        def spy(**kwargs):
            captured.append(kwargs)
            return lambda rec: ""

        monkeypatch.setattr(ra, "_build_review_action_fn", spy)

        rec = Recommendation(
            id="detail-reconcile-4",
            source="reconcile",
            severity="medium",
            step_id=4,
            title="re-audit step 4",
            body="run detail-reconcile",
            suggested_action="plan-tool detail demo --reconcile --step 4",
        )
        action(rec)
        assert captured, "recursive sub-walk build was not invoked"
        assert all(c.get("allow_split") is True for c in captured)
        assert all(
            c.get("allow_structural_verdict") is False for c in captured
        )

    def test_non_structural_verdict_never_escalates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_apply(plan_path, **kwargs):
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="- a\n+ b\n",
                summary="ok", pre_snapshot={}, introduced_findings=(),
                resolved_findings=(),
            )

        monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        action = self._build(tmp_path, monkeypatch)
        action(_structural_rec())
        assert calls == []  # ordinary APPLIED never escalates

    def test_builder_allow_split_defaults_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        calls = _stub_escalate(monkeypatch, _escalate_result("recommended",
            recommendation=SimpleNamespace(suggested_action="plan-tool split")))
        action = self._build(tmp_path, monkeypatch)  # no allow_split kwarg
        action(_structural_rec())
        assert calls[0]["allow_split"] is False  # recommend-only by default

    # -- Full post-call WalkState pins (halt_on_applied=False lane) ----------
    # This lane is only reached in production through the BLOCKED-STRUCTURAL
    # arm of _dispatch_apply_finding, which pre-sets ``apply_skip=True`` before
    # delegating; the escalation applied branch never resets it, so an applied
    # split here ends ``apply_skip=True`` (records ``skip``) — the opposite
    # disposition from the granularity-split router (halt_on_applied=True),
    # which leaves it False. Neither halts, records the finding id, nor sets
    # ``apply_failed`` in this lane.

    def test_escalation_applied_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied", target_id=4))
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, state=state)
        rec = _structural_rec(step_id=4)
        result = action(rec)
        assert "applied a 2-step split at step 4" in result
        # apply_skip True (pre-set by the BLOCKED-STRUCTURAL arm); no halt, no
        # recorded id (escalation never records), apply_failed untouched.
        _assert_walk_state(state, apply_skip=True)
        assert rec.id not in state.applied_structural_finding_ids

    def test_escalation_applied_without_reconcile_guard_does_not_refresh(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(lock):  # pragma: no cover - must never be reached
            raise AssertionError("refresh_snapshot fired without a guard")

        monkeypatch.setattr(
            "plan_tool.drift_detection.refresh_snapshot", boom
        )
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied", target_id=4))
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, state=state)  # no guard
        result = action(_structural_rec(step_id=4))
        assert "applied a 2-step split at step 4" in result
        _assert_walk_state(state, apply_skip=True)

    def test_escalation_non_applied_outcomes_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for res in (
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 4 ..."
                ),
            ),
            _escalate_result("unsafe", blocking=[5, 6], recommendation=None),
            _escalate_result("proposal-unusable"),
            _escalate_result("step-missing"),
        ):
            _stub_blocked_structural(monkeypatch)
            _stub_escalate(monkeypatch, res)
            state = WalkState()
            action = self._build(tmp_path, monkeypatch, state=state)
            action(_structural_rec(step_id=4))
            _assert_walk_state(state, apply_skip=True)

    def test_escalation_plan_level_none_leaves_no_halt_no_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied"))
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, state=state)
        result = action(
            _structural_rec(step_id=None, source="plan-completeness")
        )
        assert "re-decompose through a session-directed edit" in result
        _assert_walk_state(state, apply_skip=True)


def _split_finding_rec(*, step_id=4, severity="medium"):
    """A persisted ``medium`` ``granularity-split`` MIXED-STEP finding — the
    shape step 2 writes into the completeness sidecar."""
    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

    suffix = step_id if step_id is not None else "plan"
    return Recommendation(
        id=f"granularity-split-{suffix}",
        source=GRANULARITY_SPLIT_SOURCE,
        severity=severity,
        step_id=step_id,
        title="step mixes a refactor with new behavior",
        body="split the refactor half from the feature half",
        suggested_action="plan-tool split demo --step 4",
    )


_SPLIT_OPT_IN = frozenset({"granularity-split"})


class TestSplitEscalationDispatch:
    """A persisted ``medium`` ``granularity-split`` finding routes through the
    escalate-to-split bridge (not ``apply_finding``) when the completeness-apply
    lane opts the source in, and an applied split halts the walk."""

    def _build(self, tmp_path, monkeypatch, **kwargs):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        kwargs.setdefault("extra_apply_sources", _SPLIT_OPT_IN)
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            **kwargs,
        )

    def test_granularity_split_routes_to_escalate_to_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_escalate(
            monkeypatch, _escalate_result("applied", target_id=4)
        )
        action = self._build(tmp_path, monkeypatch, allow_split=True)
        action(_split_finding_rec(step_id=4))
        assert len(calls) == 1
        assert calls[0]["step_id"] == 4
        assert calls[0]["allow_split"] is True
        assert calls[0]["prompt_fn"] is None

    def test_granularity_split_never_calls_apply_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom_apply(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("apply_finding ran on a structural split")

        monkeypatch.setattr("plan_tool.launcher.apply_finding", boom_apply)
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        action = self._build(tmp_path, monkeypatch, allow_split=True)
        action(_split_finding_rec())
        assert len(calls) == 1  # dispatched to the bridge, not apply_finding

    def test_granularity_split_applied_halts_walk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_escalate(
            monkeypatch, _escalate_result("applied", target_id=4)
        )
        state = WalkState()
        action = self._build(
            tmp_path, monkeypatch, allow_split=True, state=state,
        )
        result = action(_split_finding_rec(step_id=4))
        assert state.halt_requested is True
        assert state.halt_apply_landed is True
        # applied is the only outcome that leaves apply_skip False (resolved) —
        # the split landed, so the walk records it as applied.
        assert state.apply_skip is False
        assert "applied a 2-step split at step 4" in result
        assert "re-run" in result and "re-walk" in result

    def test_granularity_split_recommended_does_not_halt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 4 --into ..."
                ),
            ),
        )
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, state=state)
        result = action(_split_finding_rec())
        assert state.halt_requested is False
        assert state.halt_apply_landed is False
        # No split landed — the walk must record this as skipped, not applied,
        # or the next completeness-apply run pre-skips it as "already applied"
        # and the required split is silently lost.
        assert state.apply_skip is True
        assert "plan-tool split demo --step 4" in result

    def test_granularity_split_yes_to_all_forces_recommend_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_escalate(
            monkeypatch,
            _escalate_result(
                "recommended",
                recommendation=SimpleNamespace(suggested_action="plan-tool split"),
            ),
        )
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, monkeypatch, allow_split=True, state=state,
        )
        action(_split_finding_rec())
        # A blanket fast-forward never auto-confirms an irreversible split.
        assert calls[0]["allow_split"] is False

    def test_granularity_split_step_id_none_reports_redecompose(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, allow_split=True, state=state)
        result = action(_split_finding_rec(step_id=None))
        assert calls == []  # never dispatched
        assert "re-decompose through a session-directed edit" in result
        # Plan-level verdict resolved nothing — must record as skipped, not
        # applied (else the next completeness-apply run pre-skips it).
        assert state.apply_skip is True

    def test_granularity_split_applied_does_not_record_finding_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_escalate(
            monkeypatch, _escalate_result("applied", target_id=4)
        )
        state = WalkState()
        action = self._build(
            tmp_path, monkeypatch, allow_split=True, state=state,
        )
        rec = _split_finding_rec(step_id=4)
        action(rec)
        # halt_on_applied=True halts and leaves apply_skip False (this route
        # never pre-sets it), but escalation — unlike merge/reground — does NOT
        # record the finding id, and apply_failed stays False.
        _assert_walk_state(
            state, apply_skip=False,
            halt_requested=True, halt_apply_landed=True,
        )
        assert rec.id not in state.applied_structural_finding_ids

    def test_split_fresh_signature_escalates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A split whose target step still holds its (id → title) identity must
        # actuate even after an unrelated earlier apply rewrote the plan — the
        # precise per-directive guard, not the coarse whole-plan fingerprint.
        plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4"), (5, "Step 5")]
        )
        rec = _stamp(_split_finding_rec(step_id=4), plan)
        # An unrelated edit elsewhere — step 4's identity is untouched.
        _write_plan_with_steps(
            tmp_path, [(3, "A different step"), (4, "Step 4"), (5, "Step 5")]
        )
        calls = _stub_escalate(
            monkeypatch, _escalate_result("applied", target_id=4)
        )
        state = WalkState()
        action = self._build(
            tmp_path, monkeypatch, allow_split=True,
            saved_plan_fingerprint="whole-plan-fingerprint-that-wont-match",
            state=state,
        )
        result = action(rec)
        assert len(calls) == 1  # bridge reached despite the stale whole-plan fp
        assert "applied a 2-step split at step 4" in result

    def test_split_stale_signature_downgrades_to_recommend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A split whose target step moved (same id, different title) is refused:
        # never reaches the bridge, records skip, returns the re-run message.
        stamped_plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4"), (5, "Step 5")]
        )
        rec = _stamp(_split_finding_rec(step_id=4), stamped_plan)
        _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "A different step"), (5, "Step 5")]
        )
        calls = _stub_escalate(monkeypatch, _escalate_result("applied"))
        state = WalkState()
        action = self._build(
            tmp_path, monkeypatch, allow_split=True,
            saved_plan_fingerprint="",  # coarse would NOT block — only the sig does
            state=state,
        )
        result = action(rec)
        assert calls == []  # the bridge is never reached — no split
        assert state.apply_skip is True
        assert "changed since" in result

    def test_split_legacy_none_signature_still_escalates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A legacy split with no target_signature and no saved fingerprint reaches
        # the bridge unchanged — the guard is a no-op, proving no regression.
        calls = _stub_escalate(
            monkeypatch, _escalate_result("applied", target_id=4)
        )
        action = self._build(tmp_path, monkeypatch, allow_split=True)
        action(_split_finding_rec(step_id=4))
        assert len(calls) == 1

    def test_split_stale_downgrade_does_not_record_finding_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A stale downgrade leaves the walk untouched: no halt, no recorded id.
        stamped_plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4"), (5, "Step 5")]
        )
        rec = _stamp(_split_finding_rec(step_id=4), stamped_plan)
        _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "A different step"), (5, "Step 5")]
        )
        _stub_escalate(monkeypatch, _escalate_result("applied"))
        state = WalkState()
        action = self._build(
            tmp_path, monkeypatch, allow_split=True,
            saved_plan_fingerprint="", state=state,
        )
        action(rec)
        assert state.halt_requested is False
        assert state.halt_apply_landed is False
        assert rec.id not in state.applied_structural_finding_ids

    def test_blocked_structural_reconcile_path_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The BLOCKED-STRUCTURAL apply verdict route uses the same helper with
        # the default halt_on_applied=False, so an applied split there does NOT
        # halt the walk (only the completeness-apply granularity-split branch
        # passes halt_on_applied=True).
        _stub_blocked_structural(monkeypatch)
        _stub_escalate(monkeypatch, _escalate_result("applied", target_id=4))
        state = WalkState()
        action = self._build(tmp_path, monkeypatch, state=state)
        result = action(_structural_rec(step_id=4))
        assert state.halt_requested is False
        assert state.halt_apply_landed is False
        # The arm pre-set apply_skip=True before delegating and the applied
        # branch never resets it — so this route records ``skip``, the opposite
        # disposition from the halt_on_applied=True router. Step 2's kernel may
        # only ever SET apply_skip True, never reset it to False on a resolved
        # outcome, or it would silently flip this route skip→applied.
        assert state.apply_skip is True
        assert "applied a 2-step split at step 4" in result


def _one_carried(title: str = "carried gap"):
    from plan_tool.review import CarriedFinding

    return CarriedFinding(
        anchor="a", title=title, severity="high", body_excerpt="x"
    )


def _apply_finding_rec(*, rec_id="gap-1", anchor=None):
    """A ``plan-completeness`` rec — routes to ``_dispatch_apply_finding``."""
    return Recommendation(
        id=rec_id, source="plan-completeness", severity="medium", step_id=3,
        title="conceptual gap", body="the plan leaves concept X uncovered",
        suggested_action="specify how step 3 covers concept X", anchor=anchor,
    )


def _stub_apply_capturing(monkeypatch: pytest.MonkeyPatch, capture: list):
    """Stub ``apply_finding`` to record kwargs and return an APPLIED+empty-diff
    result so the dispatcher returns before any keep/revert prompt."""
    def fake_apply(plan_path, **kwargs):
        capture.append(kwargs)
        return SimpleNamespace(
            exit_code=0, verdict="APPLIED", diff_text="", summary="",
            pre_snapshot={}, introduced_findings=(), resolved_findings=(),
        )

    monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)


class TestInteractiveApplyVerdictOwnership:
    def _build(
        self,
        tmp_path,
        monkeypatch,
        *,
        isatty,
        answer="",
        resolved_findings=(),
        introduced_findings=(),
    ):
        import plan_tool.cli.review_actions as actions
        from plan_tool.launcher import DeferredApplyVerdict

        _write_file_check_plan(tmp_path, declare="files")
        plan_path = tmp_path / "demo.md"
        original = plan_path.read_text(encoding="utf-8")

        def fake_apply(path, **kwargs):
            kwargs["verdict_observer"](
                DeferredApplyVerdict(verdict="APPLIED", step_id=3)
            )
            plan_path.write_text(original + "\nkept edit\n", encoding="utf-8")
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="diff",
                summary="did it", pre_snapshot={plan_path: original},
                introduced_findings=introduced_findings,
                resolved_findings=resolved_findings,
            )

        monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)
        monkeypatch.setattr(
            "plan_tool.launcher.revert_apply_if_parse_broken", lambda result: False
        )
        monkeypatch.setattr(actions.sys, "stdin", SimpleNamespace(isatty=lambda: isatty))
        monkeypatch.setattr("builtins.input", lambda prompt: answer)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return (
            _build_review_action_fn(
                ctx=ctx, plan_path=plan_path, plan_name="demo", state=WalkState()
            ),
            plan_path,
            original,
        )

    def test_interactive_kept_edit_records_once(self, tmp_path, monkeypatch):
        import plan_tool.telemetry as telemetry

        calls = []
        monkeypatch.setattr(
            telemetry, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        action, plan_path, original = self._build(
            tmp_path, monkeypatch, isatty=False
        )
        action(_apply_finding_rec())
        assert plan_path.read_text(encoding="utf-8") != original
        assert [(call["verdict"], call["step_id"]) for call in calls] == [
            ("APPLIED", "3")
        ]

    def test_validation_lines_render_stored_confidence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        resolved = Recommendation(
            id="resolved", source="plan-completeness", severity="medium",
            step_id=3, title="Resolved gap", body="Closed.",
            confidence="supported",
        )
        introduced = Recommendation(
            id="introduced", source="plan-completeness", severity="high",
            step_id=3, title="Introduced gap", body="Open.", confidence=None,
        )
        action, _, _ = self._build(
            tmp_path,
            monkeypatch,
            isatty=False,
            resolved_findings=(resolved,),
            introduced_findings=(introduced,),
        )

        action(_apply_finding_rec())

        output = capsys.readouterr().out
        assert "✓ resolves MEDIUM: Resolved gap [confidence: supported]" in output
        assert "✗ introduces HIGH: Introduced gap [confidence: unknown]" in output

    def test_interactive_rejected_edit_records_no_applied_verdict(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.telemetry as telemetry

        calls = []
        monkeypatch.setattr(
            telemetry, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        action, plan_path, original = self._build(
            tmp_path, monkeypatch, isatty=True, answer="n"
        )
        action(_apply_finding_rec())
        assert plan_path.read_text(encoding="utf-8") == original
        assert calls == []

    def test_interactive_empty_diff_records_no_applied_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.telemetry as telemetry
        from plan_tool.launcher import DeferredApplyVerdict

        calls: list[dict] = []
        monkeypatch.setattr(
            telemetry, "record_apply_verdict", lambda *a, **kw: calls.append(kw)
        )

        def fake_apply(_path, **kwargs):
            kwargs["verdict_observer"](
                DeferredApplyVerdict(verdict="APPLIED", step_id=3)
            )
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="", summary="",
                pre_snapshot={}, introduced_findings=(), resolved_findings=(),
            )

        monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx,
            plan_path=tmp_path / "demo.md",
            plan_name="demo",
            state=WalkState(),
        )

        message = action(_apply_finding_rec(anchor="overview"))

        assert "nothing to keep" in message
        assert calls == []

    @pytest.mark.parametrize("failure_mode", ["nonzero", "launcher-error"])
    def test_interactive_failure_records_invocation_failed_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure_mode: str,
    ) -> None:
        import plan_tool.telemetry as telemetry
        from plan_tool.launcher import DeferredApplyVerdict, LauncherError

        calls: list[dict] = []
        monkeypatch.setattr(
            telemetry, "record_apply_verdict", lambda *a, **kw: calls.append(kw)
        )

        def fake_apply(_path, **kwargs):
            kwargs["verdict_observer"](
                DeferredApplyVerdict(verdict="INVOCATION-FAILED", step_id=3)
            )
            if failure_mode == "launcher-error":
                raise LauncherError("backend failed")
            return SimpleNamespace(exit_code=7, verdict="INVOCATION-FAILED")

        monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx,
            plan_path=tmp_path / "demo.md",
            plan_name="demo",
            state=WalkState(),
        )

        message = action(_apply_finding_rec(anchor="overview"))

        assert "error" in message or "code 7" in message
        assert len(calls) == 1
        assert {
            key: calls[0][key]
            for key in ("plan_slug", "verdict", "step_id", "anchor")
        } == {
            "plan_slug": "demo",
            "verdict": "INVOCATION-FAILED",
            "step_id": "3",
            "anchor": "overview",
        }
        assert calls[0]["plan_fingerprint"]


class TestApplyTelemetryForwarding:
    def test_apply_dispatch_hoists_and_forwards_telemetry_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.review_actions as actions

        fingerprint_calls: list[Path] = []
        monkeypatch.setattr(
            actions,
            "compute_plan_fingerprint",
            lambda path: fingerprint_calls.append(path) or "shared-review-fp",
        )
        apply_calls: list[dict] = []
        _stub_apply_capturing(monkeypatch, apply_calls)
        plan_path = tmp_path / "demo.md"
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="demo", state=WalkState()
        )

        action(_apply_finding_rec(rec_id="gap-a", anchor="overview"))
        action(_apply_finding_rec(rec_id="gap-b"))

        assert [call["anchor"] for call in apply_calls] == ["overview", ""]
        assert {call["plan_fingerprint"] for call in apply_calls} == {
            "shared-review-fp"
        }
        assert all(call["record_verdict"] is False for call in apply_calls)
        assert all(call["verdict_observer"] is not None for call in apply_calls)
        assert fingerprint_calls == [plan_path]

    def test_apply_dispatch_fingerprint_failure_is_best_effort(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.review_actions as actions

        def fail_fingerprint(_path):
            raise OSError("fingerprint unavailable")

        monkeypatch.setattr(actions, "compute_plan_fingerprint", fail_fingerprint)
        apply_calls: list[dict] = []
        _stub_apply_capturing(monkeypatch, apply_calls)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx,
            plan_path=tmp_path / "demo.md",
            plan_name="demo",
            state=WalkState(),
        )
        message = action(_apply_finding_rec(anchor="overview"))

        assert message == (
            "apply-finding reported APPLIED but the plan file didn't change; "
            "nothing to keep"
        )
        assert [(call["anchor"], call["plan_fingerprint"]) for call in apply_calls] == [
            ("overview", "")
        ]
        assert apply_calls[0]["record_verdict"] is False


class TestCarriedFindingsForwarding:
    """``_build_review_action_fn`` threads ``carried_findings`` (a static
    sequence or a zero-arg provider) into every ``apply_finding`` call, and
    nested detail-reconcile subwalks inherit it."""

    def test_builder_forwards_carried_findings_to_apply_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list = []
        _stub_apply_capturing(monkeypatch, captured)
        carried = [_one_carried()]
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=WalkState(), carried_findings=carried,
        )
        action(_apply_finding_rec())
        assert captured[0]["carried_findings"] is carried

    def test_builder_resolves_carried_findings_provider_per_apply(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list = []
        _stub_apply_capturing(monkeypatch, captured)
        box: dict = {"value": []}
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return box["value"]

        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=WalkState(), carried_findings=provider,
        )
        action(_apply_finding_rec())
        # Mutate the provider's backing state between applies …
        box["value"] = [_one_carried("second-apply gap")]
        action(_apply_finding_rec())
        # … the provider is resolved once per apply, reflecting the latest.
        assert calls["n"] == 2
        assert captured[0]["carried_findings"] == []
        assert captured[1]["carried_findings"] == box["value"]

    def test_builder_defaults_carried_findings_to_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list = []
        _stub_apply_capturing(monkeypatch, captured)
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        action = _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=WalkState(),
        )  # no carried_findings kwarg
        action(_apply_finding_rec())
        assert captured[0]["carried_findings"] == ()

    def test_detail_reconcile_subwalk_inherits_carried_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.review_actions as ra
        from plan_tool.cli import reconcile

        sentinel = [_one_carried()]
        saved = SimpleNamespace(recommendations=[SimpleNamespace(id="r1")])
        monkeypatch.setattr(
            reconcile, "_find_saved_detail_reconcile_for_step",
            lambda *a, **k: (tmp_path / "saved.json", saved),
        )
        monkeypatch.setattr(
            reconcile, "_walk_with_reconcile_phase", lambda *a, **k: None,
        )

        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        # yes_to_all takes the reuse path without a TTY prompt.
        state = WalkState(yes_to_all=True)
        action = _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=state, carried_findings=sentinel,
        )

        captured: dict = {}

        def spy(*args, **kwargs):
            captured["carried_findings"] = kwargs.get("carried_findings")
            return lambda rec: "sub"

        # The dispatcher resolves the recursive builder as a module global at
        # call time, so patching the module attribute redirects the sub-build.
        monkeypatch.setattr(ra, "_build_review_action_fn", spy)
        rec = Recommendation(
            id="dr-3", source="detail-reconcile", severity="high", step_id=3,
            title="reconcile step 3", body="audit plan vs code",
            suggested_action="plan-tool detail demo --reconcile --step 3",
        )
        action(rec)
        assert captured["carried_findings"] is sentinel


# ---------------------------------------------------------------------------
# Step 5: re-ground remedy dispatch — a ``granularity-merge`` finding carrying
# a ``reground`` directive routes to ``reground_bridge`` (mark-done), driven by
# the directive kind (never the source), gated by ``allow_structural_remedy``.
# ---------------------------------------------------------------------------


_MANUAL_RUN_NOTICE = (
    "suggested action isn't a recognized reconcile or detail "
    "invocation; run it manually in another shell"
)


def _reground_rec(*, step_ids=(3, 4, 5)):
    """A ``granularity-merge`` re-ground finding carrying step 4's directive
    marker — the shape ``_reground_already_built_recommendation`` emits
    (plan-wide, ``step_id=None``, ``info`` severity)."""
    from plan_tool.review import MERGE_ACTION_REGROUND, render_merge_action

    ids = ", ".join(str(i) for i in step_ids)
    suggested = (
        f"re-baseline the set against HEAD: mark steps {ids} done. "
        + render_merge_action(MERGE_ACTION_REGROUND, list(step_ids))
    )
    return Recommendation(
        id="granularity-merge-reground-abc",
        source="granularity-merge",
        severity="info",
        step_id=None,
        title=f"Re-ground: steps {ids} appear already-built",
        body="the code already implements these distinct steps",
        suggested_action=suggested,
    )


def _reground_result(
    outcome,
    *,
    requested_ids=(3, 4, 5),
    marked_ids=(),
    new_current_id=None,
    completed=False,
    blocking=(),
    seed_path=None,
):
    return SimpleNamespace(
        outcome=outcome,
        requested_ids=list(requested_ids),
        marked_ids=list(marked_ids),
        new_current_id=new_current_id,
        completed=completed,
        blocking=list(blocking),
        seed_path=seed_path,
    )


def _stub_reground_bridge(monkeypatch: pytest.MonkeyPatch, result):
    """Patch ``reground_bridge`` on its **owning** module and record kwargs.

    The dispatcher resolves it via a body-local import at call time, so
    patching ``plan_tool.reground.reground_bridge`` intercepts it. The bridge
    is deterministic and spends no Claude, so no invoker stub is needed."""
    calls: list[dict] = []

    def fake(plan_path, **kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr("plan_tool.reground.reground_bridge", fake)
    return calls


def _write_plan_with_steps(tmp_path: Path, steps) -> "Plan":
    """Write ``demo.md`` with the given ``(id, title)`` steps (all pending) and
    return the parsed ``Plan`` — the on-disk plan the per-directive staleness
    guard re-parses and re-hashes against a finding's ``target_signature``."""
    from plan_tool.parser import parse_plan

    body = "---\ntitle: Demo\nstatus: in-progress\npriority: medium\nsteps:\n"
    for step_id, title in steps:
        body += f"- id: {step_id}\n  title: {title}\n  status: pending\n"
    body += "---\n# Demo\n"
    (tmp_path / "demo.md").write_text(body, encoding="utf-8")
    return parse_plan(tmp_path / "demo.md")


def _stamp(rec, plan):
    """Return ``rec`` with the ``target_signature`` step 2 would stamp for its
    own targets against ``plan`` — reuses the shared recovery + hasher so the
    stamp and the guard's recompute can never diverge."""
    from dataclasses import replace

    from plan_tool.review_walk import (
        compute_target_signature,
        directive_target_ids,
    )

    ids = directive_target_ids(rec)
    return replace(rec, target_signature=compute_target_signature(plan, ids))


class TestRegroundRemedyDispatch:
    """Applying a ``granularity-merge`` finding with a ``reground`` directive
    calls ``reground_bridge`` with the directive's step ids and maps the
    frozen outcome to a one-line walk status + annotation."""

    def _build(self, tmp_path: Path, **kwargs):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            **kwargs,
        )

    def test_reground_directive_routes_to_reground_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended", marked_ids=(3, 4, 5))
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert len(calls) == 1
        assert calls[0]["step_ids"] == [3, 4, 5]

    def test_missing_plan_file_downgrades_not_crashes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The precise guard parses the plan to re-hash the target signature.
        # If the plan was moved/deleted between audit and apply (exactly the
        # drift the guard defends against), parse_plan raises FileNotFoundError
        # — the guard must degrade to the coarse fallback (stale → recommend-
        # only), never crash the walk.
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended", marked_ids=(3, 4, 5))
        )
        plan = _write_plan_with_steps(
            tmp_path, [(3, "a"), (4, "b"), (5, "c")]
        )
        rec = _stamp(_reground_rec(step_ids=(3, 4, 5)), plan)
        (tmp_path / "demo.md").unlink()  # plan gone between audit and apply
        state = WalkState()
        # EMPTY saved fingerprint — the reconcile / completeness-apply lanes
        # pass none. The guard must still return stale on a gone plan (parse
        # failure → stale unconditionally), or the bridge re-parses and crashes.
        action = self._build(
            tmp_path, allow_structural_remedy=True,
            saved_plan_fingerprint="",
            state=state,
        )
        result = action(rec)  # must not raise
        assert calls == []  # gone plan → stale → bridge not actuated
        assert state.apply_skip is True
        assert "recommend" in result.lower() or "re-run" in result.lower()

    def test_step_ids_forwarded_from_directive_not_rec_step_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(monkeypatch, _reground_result("recommended"))
        rec = _reground_rec(step_ids=(2, 6, 9))
        # The re-ground finding is plan-wide: rec.step_id is None, so the full
        # target set is recoverable only from the directive.
        assert rec.step_id is None
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(rec)
        assert calls[0]["step_ids"] == [2, 6, 9]

    def test_opt_in_forced_off_under_yes_to_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(monkeypatch, _reground_result("recommended"))
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        action(_reground_rec())
        # A blanket fast-forward never auto-confirms an irreversible mutation.
        assert calls[0]["allow_reground"] is False
        assert calls[0]["yes"] is False

    def test_opt_in_passed_through_when_allowed_and_not_fast_forward(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(monkeypatch, _reground_result("recommended"))
        state = WalkState(yes_to_all=False)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        action(_reground_rec())
        assert calls[0]["allow_reground"] is True
        assert calls[0]["yes"] is False

    def test_opt_in_defaults_off_and_ignores_allow_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(monkeypatch, _reground_result("recommended"))
        # allow_structural_remedy left at its False default; allow_split ON —
        # the re-ground opt-in is decoupled from the split flag.
        action = self._build(tmp_path, allow_split=True)
        action(_reground_rec())
        assert calls[0]["allow_reground"] is False

    def test_applied_outcome_records_applied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(
            monkeypatch, _reground_result("applied", marked_ids=(3, 4, 5))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        # applied is the only outcome that leaves apply_skip False (resolved).
        assert state.apply_skip is False
        assert "re-grounded" in result
        assert "3, 4, 5" in result

    def test_recommended_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(
            monkeypatch, _reground_result("recommended", marked_ids=(3, 4))
        )
        state = WalkState()
        # Not opted in → the bridge recommends; no edit landed.
        action = self._build(tmp_path, state=state)
        result = action(_reground_rec(step_ids=(3, 4)))
        assert state.apply_skip is True
        assert "--apply-structural" in result

    def test_unsafe_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(
            monkeypatch, _reground_result("unsafe", blocking=(4,))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_reground_rec())
        assert state.apply_skip is True
        assert "unsafe" in result and "4" in result

    def test_reground_noop_outcome_records_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A noop means every named step is already done — the re-ground's
        # desired end state already holds, so the finding is resolved, not
        # skipped (this also prevents a re-dispatch after an apply via the
        # walk's r/run key from mislabelling the completed re-ground as skip).
        _stub_reground_bridge(monkeypatch, _reground_result("noop"))
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_reground_rec())
        assert state.apply_skip is False
        assert "noop" in result

    def test_stale_plan_fingerprint_downgrades_to_recommend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A saved finding whose fingerprint no longer matches the plan on disk
        # (the plan was edited/renumbered since it was computed) must NOT
        # actuate — its ids may now name different steps. Downgrade, no mutation.
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_reground_bridge(monkeypatch, _reground_result("applied"))
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(_reground_rec())
        assert calls == []  # the bridge is never called — no mark-done
        assert state.apply_skip is True
        assert "changed since" in result

    def test_empty_saved_fingerprint_does_not_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty saved fingerprint (legacy/unset) carries no staleness info,
        # so the guard must not block — the bridge is reached normally.
        (tmp_path / "demo.md").write_text("# demo plan\n", encoding="utf-8")
        calls = _stub_reground_bridge(monkeypatch, _reground_result("applied"))
        action = self._build(
            tmp_path, allow_structural_remedy=True, saved_plan_fingerprint=""
        )
        action(_reground_rec())
        assert len(calls) == 1  # guard skipped, bridge actuated

    def test_stale_reground_with_coincidental_done_ids_downgrades(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A genuinely-stale re-ground (plan renumbered since it was computed)
        # whose saved ids COINCIDENTALLY now land on DONE steps must be
        # DOWNGRADED to recommend-only, not silently swallowed as resolved — the
        # DONE steps may not be the ones the finding meant. The stale-guard runs
        # before any noop disposition, so the bridge is never reached.
        (tmp_path / "demo.md").write_text(
            "---\ntitle: Demo\nstatus: in-progress\npriority: medium\nsteps:\n"
            + "".join(
                f"- id: {i}\n  title: Step {i}\n  status: done\n"
                for i in (1, 2, 3, 4, 5)
            )
            + "---\n# Demo\n",
            encoding="utf-8",
        )
        calls = _stub_reground_bridge(monkeypatch, _reground_result("noop"))
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls == []  # stale-guard fires before the bridge
        assert state.apply_skip is True  # downgraded, not resolved
        assert "changed since" in result

    def test_applied_reground_resolves_on_redispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defect B (session signal, not fingerprint): a re-ground actuated
        # earlier in THIS walk via the r/run key rewrote the plan, so its
        # fingerprint no longer matches. The 'a'-key re-dispatch must resolve
        # from ``applied_structural_finding_ids`` — NOT trip the stale-guard and
        # mislabel the completed re-ground as ``skip``.
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_reground_bridge(monkeypatch, _reground_result("applied"))
        state = WalkState()
        rec = _reground_rec(step_ids=(3, 4, 5))
        state.applied_structural_finding_ids.add(rec.id)  # applied earlier this walk
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(rec)
        assert calls == []  # session signal short-circuits before guard + bridge
        assert state.apply_skip is False  # resolved
        assert "already done" in result
        assert "changed since" not in result

    # --- Re-baseline disposition selector (step 6) --------------------------

    def test_default_forwards_mark_done_disposition(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Flag left at its default → the bridge gets the mark-done disposition,
        # so every existing caller keeps today's behavior.
        from plan_tool.reground import DISPOSITION_MARK_DONE

        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["disposition"] == DISPOSITION_MARK_DONE

    def test_rebaseline_flag_forwards_rebaseline_disposition(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # reground_rebaseline=True → the bridge gets the re-baseline disposition.
        from plan_tool.reground import DISPOSITION_REBASELINE

        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(
            tmp_path, allow_structural_remedy=True, reground_rebaseline=True
        )
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["disposition"] == DISPOSITION_REBASELINE

    def test_repo_root_forwarded_to_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # repo_root is always forwarded (harmless on mark-done; required for the
        # re-baseline arm to place the seed).
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(
            tmp_path, allow_structural_remedy=True, reground_rebaseline=True
        )
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["repo_root"] == tmp_path

    def test_rebaseline_flag_does_not_enable_reground(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The flag selects disposition only — with no enable opt-in the
        # re-ground stays recommend-only (allow_reground False).
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(tmp_path, reground_rebaseline=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["allow_reground"] is False
        assert calls[0]["disposition"] == "re-baseline"

    def test_applied_rebaseline_message_names_seed_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An applied re-baseline outcome names the written seed and tells the
        # operator it supersedes the plan; an applied mark-done outcome
        # (seed_path=None) keeps the unchanged message.
        seed = tmp_path / "plan-seeds" / "demo-reground-3-5.md"
        _stub_reground_bridge(
            monkeypatch,
            _reground_result("applied", marked_ids=(3, 4, 5), seed_path=seed),
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        assert str(seed) in result
        assert "supersedes" in result
        assert "create --from-existing" in result

        # mark-done applied (no seed) — message names no seed.
        _stub_reground_bridge(
            monkeypatch, _reground_result("applied", marked_ids=(3, 4, 5))
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        assert "supersedes" not in result
        assert "re-baseline seed" not in result

    def test_matching_target_signature_actuates_despite_plan_edit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The mixed-walk case the step fixes: an earlier apply rewrote the plan
        # so ``saved_plan_fingerprint`` no longer matches the whole-plan
        # fingerprint, but this directive's OWN targets are untouched — the
        # stamped ``target_signature`` still equals the recomputed one — so it
        # must actuate, not downgrade.
        plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4"), (5, "Step 5")]
        )
        rec = _stamp(_reground_rec(step_ids=(3, 4, 5)), plan)
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("applied", marked_ids=(3, 4, 5))
        )
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="whole-plan-fingerprint-that-wont-match",
            state=state,
        )
        result = action(rec)
        assert len(calls) == 1  # bridge reached despite the stale whole-plan fp
        assert state.apply_skip is False  # resolved
        assert "re-grounded" in result

    def test_mismatched_target_signature_downgrades(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A target step's title changed on disk since the finding was stamped,
        # so the recomputed signature differs from the saved one — the directive
        # is stale and must downgrade to recommend-only, no mutation.
        stamped_plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4"), (5, "Step 5")]
        )
        rec = _stamp(_reground_rec(step_ids=(3, 4, 5)), stamped_plan)
        # Rewrite the plan so step 4's identity moved under the same ids.
        _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "A different step"), (5, "Step 5")]
        )
        calls = _stub_reground_bridge(monkeypatch, _reground_result("applied"))
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="",  # coarse would NOT block — only the sig does
            state=state,
        )
        result = action(rec)
        assert calls == []  # the bridge is never reached — no mark-done
        assert state.apply_skip is True
        assert "changed since" in result

    def test_step_missing_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(
            monkeypatch, _reground_result("step-missing", blocking=(9,))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_reground_rec())
        assert state.apply_skip is True
        assert "9" in result

    # -- Full post-call WalkState pins --------------------------------------
    # Re-ground never halts and never refreshes the drift baseline; an applied
    # re-ground records the finding id (so an r-then-a re-dispatch resolves via
    # the session signal), a noop resolves without recording it, and every
    # non-resolved outcome sets apply_skip. None touch apply_failed.

    def test_reground_applied_records_id_and_no_halt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(
            monkeypatch, _reground_result("applied", marked_ids=(3, 4, 5))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        rec = _reground_rec(step_ids=(3, 4, 5))
        action(rec)
        _assert_walk_state(state, apply_skip=False, applied_ids={rec.id})

    def test_reground_applied_does_not_refresh_drift(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(lock):  # pragma: no cover - must never be reached
            raise AssertionError("re-ground must not refresh the drift baseline")

        monkeypatch.setattr(
            "plan_tool.drift_detection.refresh_snapshot", boom
        )
        _stub_reground_bridge(
            monkeypatch, _reground_result("applied", marked_ids=(3, 4, 5))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        assert "re-grounded" in result

    def test_reground_noop_leaves_id_set_empty_no_halt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_reground_bridge(monkeypatch, _reground_result("noop"))
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        action(_reground_rec())
        _assert_walk_state(state, apply_skip=False)

    def test_reground_non_applied_outcomes_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for res in (
            _reground_result("recommended", marked_ids=(3, 4)),
            _reground_result("unsafe", blocking=(4,)),
            _reground_result("step-missing", blocking=(9,)),
        ):
            _stub_reground_bridge(monkeypatch, res)
            state = WalkState()
            action = self._build(
                tmp_path, allow_structural_remedy=True, state=state
            )
            action(_reground_rec())
            _assert_walk_state(state, apply_skip=True)

    def test_reground_session_short_circuit_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # rec.id already in the session set → resolved without touching the
        # bridge; apply_skip stays False (resolved), no halt, id set preserved.
        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("reground_bridge must not run on a session hit")

        monkeypatch.setattr("plan_tool.reground.reground_bridge", boom)
        state = WalkState()
        rec = _reground_rec(step_ids=(3, 4, 5))
        state.applied_structural_finding_ids.add(rec.id)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(rec)
        assert "already done" in result
        _assert_walk_state(state, apply_skip=False, applied_ids={rec.id})


# ---------------------------------------------------------------------------
# Merge remedy dispatch — a ``granularity-merge`` finding carrying a ``merge``
# directive routes to ``merge_bridge`` (fold steps), driven by the directive
# kind (never the source), gated by ``allow_structural_remedy``. Split from the
# re-ground branch by directive kind so neither remedy steals the other's
# finding.
# ---------------------------------------------------------------------------


def _merge_rec(*, step_ids=(3, 4), rec_id="granularity-merge-3-4"):
    """A ``granularity-merge`` pairwise finding carrying step 1's ``merge``
    directive marker — ``step_id`` is the low member id (not the full set), the
    severity stays ``info``."""
    from plan_tool.review import MERGE_ACTION_MERGE, render_merge_action

    lo, hi = step_ids[0], step_ids[-1]
    suggested = (
        f"Consider merging steps {lo} and {hi}. "
        + render_merge_action(MERGE_ACTION_MERGE, step_ids)
    )
    return Recommendation(
        id=rec_id,
        source="granularity-merge",
        severity="info",
        step_id=step_ids[0],
        title=f"Steps {lo}-{hi} may be over-fragmented",
        body="adjacent dependent steps",
        suggested_action=suggested,
    )


def _merge_bridge_result(
    outcome,
    *,
    requested_ids=(3, 4),
    folded_ids=(4,),
    merged_id=3,
    merged_title="Merged step",
    blocking_ids=(),
    apply_error=None,
):
    merge_result = None
    # A post-fold authoring failure carries apply_error and no merge_result.
    if outcome in ("applied", "recommended") and apply_error is None:
        merge_result = SimpleNamespace(
            folded_ids=list(folded_ids),
            merged_id=merged_id,
            merged_title=merged_title,
        )
    return SimpleNamespace(
        outcome=outcome,
        requested_ids=list(requested_ids),
        merge_result=merge_result,
        blocking_ids=list(blocking_ids),
        apply_error=apply_error,
    )


def _stub_merge_bridge(monkeypatch: pytest.MonkeyPatch, result):
    """Patch ``merge_bridge`` on its **owning** module and record kwargs.

    The dispatcher resolves it via a body-local import at call time, so patching
    ``plan_tool.detail.merge_bridge`` intercepts it — never a
    ``plan_tool.cli.review_actions`` global."""
    calls: list[dict] = []

    def fake(plan_path, **kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr("plan_tool.detail.merge_bridge", fake)
    return calls


class TestMergeRemedyDispatch:
    """Applying a ``granularity-merge`` finding with a ``merge`` directive calls
    ``merge_bridge`` with the directive's step ids and maps the frozen outcome
    to a one-line walk status + annotation."""

    def _build(self, tmp_path: Path, **kwargs):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            **kwargs,
        )

    def test_merge_directive_routes_to_merge_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(_merge_rec(step_ids=(3, 4)))
        assert len(calls) == 1
        assert calls[0]["merge_ids"] == [3, 4]

    def test_merge_step_ids_forwarded_from_directive_not_rec_step_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        rec = _merge_rec(step_ids=(3, 4))
        # A pairwise merge finding carries only the low member id on step_id;
        # the full fold set is recoverable only from the directive.
        assert rec.step_id == 3
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(rec)
        assert calls[0]["merge_ids"] == [3, 4]

    def test_merge_opt_in_forced_off_under_yes_to_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        action(_merge_rec())
        # A blanket fast-forward never auto-confirms an irreversible fold.
        assert calls[0]["allow_merge"] is False
        assert calls[0]["yes"] is False

    def test_merge_opt_in_passed_when_apply_structural_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        state = WalkState(yes_to_all=False)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        action(_merge_rec())
        assert calls[0]["allow_merge"] is True
        assert calls[0]["yes"] is False

    def test_merge_applied_outcome_records_applied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_merge_bridge(
            monkeypatch,
            _merge_bridge_result("applied", folded_ids=(4,), merged_id=3),
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        rec = _merge_rec(step_ids=(3, 4))
        result = action(rec)
        # applied is the only outcome that leaves apply_skip False (resolved).
        assert state.apply_skip is False
        assert "merged steps 4 into step 3" in result
        # An applied merge renumbers the plan, so the walk must HALT (keeping
        # this rec's applied status via halt_apply_landed) and record the
        # finding id so a re-dispatch is a noop, not a stale-guard misfire.
        assert state.halt_requested is True
        assert state.halt_apply_landed is True
        assert rec.id in state.applied_structural_finding_ids

    def test_merge_applied_r_then_a_is_noop_not_stale_misfire(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # r-then-a on the same merge finding: the first apply folds the plan
        # (changing its fingerprint), so on the second dispatch the stale-guard
        # WOULD fire — but the session signal short-circuits FIRST, resolving it
        # as a noop instead of mislabeling the completed merge "skipped". Seed
        # the session set (the applied branch does this) and a non-matching
        # fingerprint (the post-fold plan) to assert the guard ordering.
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("applied", folded_ids=(4,), merged_id=3)
        )
        rec = _merge_rec(step_ids=(3, 4))
        state = WalkState()
        state.applied_structural_finding_ids.add(rec.id)  # applied earlier this walk
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="stale-after-fold",  # won't match the plan
            state=state,
        )
        result = action(rec)
        assert "already folded" in result
        assert "skipped" not in result  # NOT the stale-guard misfire
        assert calls == []  # resolved without re-folding
        assert state.apply_skip is False  # a noop resolve, not a skip

    def test_merge_applied_authoring_failure_still_applied_and_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # merge_bridge folded the plan but re-authoring the merged step failed:
        # outcome is still applied (the structural fold landed), the walk halts,
        # and the message tells the operator to finish authoring by hand.
        _stub_merge_bridge(
            monkeypatch,
            _merge_bridge_result("applied", apply_error="backend exited 1"),
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_merge_rec(step_ids=(3, 4)))
        assert state.apply_skip is False
        assert state.halt_requested is True
        assert "backend exited 1" in result
        assert "plan-tool detail" in result

    def test_merge_recommended_message_omits_include_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Merge directives stay visible under the default info hide, so the
        # recommend-only guidance must NOT tell the operator to add
        # --include-info (only re-ground keeps that requirement).
        _stub_merge_bridge(monkeypatch, _merge_bridge_result("recommended"))
        action = self._build(tmp_path)
        result = action(_merge_rec())
        assert "--apply-structural" in result
        assert "--include-info" not in result

    def test_merge_recommended_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        state = WalkState()
        # Not opted in → the bridge recommends; no edit landed.
        action = self._build(tmp_path, state=state)
        result = action(_merge_rec())
        assert state.apply_skip is True
        assert "--apply-structural" in result

    def test_merge_unsafe_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("unsafe", blocking_ids=(4,))
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_merge_rec())
        assert state.apply_skip is True
        assert "unsafe" in result and "4" in result

    def test_merge_invalid_outcome_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_merge_bridge(monkeypatch, _merge_bridge_result("invalid"))
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(_merge_rec(step_ids=(3, 4)))
        assert state.apply_skip is True
        assert "invalid" in result

    # -- Full post-call WalkState pins --------------------------------------
    # An applied merge halts (the fold renumbers the plan), records the finding
    # id, and never refreshes the drift baseline; a non-applied outcome sets
    # apply_skip. None of these set apply_failed.

    def test_merge_applied_does_not_refresh_drift(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(lock):  # pragma: no cover - must never be reached
            raise AssertionError("merge must not refresh the drift baseline")

        monkeypatch.setattr(
            "plan_tool.drift_detection.refresh_snapshot", boom
        )
        _stub_merge_bridge(
            monkeypatch,
            _merge_bridge_result("applied", folded_ids=(4,), merged_id=3),
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        rec = _merge_rec(step_ids=(3, 4))
        result = action(rec)
        assert "merged steps 4 into step 3" in result
        _assert_walk_state(
            state, apply_skip=False,
            halt_requested=True, halt_apply_landed=True,
            applied_ids={rec.id},
        )

    def test_merge_applied_apply_failed_stays_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An applied fold whose post-fold re-authoring errored is still applied
        # (the structural fold landed): halt + id recorded, apply_failed False.
        _stub_merge_bridge(
            monkeypatch,
            _merge_bridge_result("applied", apply_error="backend exited 1"),
        )
        state = WalkState()
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        rec = _merge_rec(step_ids=(3, 4))
        result = action(rec)
        assert "backend exited 1" in result
        _assert_walk_state(
            state, apply_skip=False,
            halt_requested=True, halt_apply_landed=True,
            applied_ids={rec.id},
        )

    def test_merge_non_applied_outcomes_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for res in (
            _merge_bridge_result("recommended"),
            _merge_bridge_result("unsafe", blocking_ids=(4,)),
            _merge_bridge_result("invalid"),
        ):
            _stub_merge_bridge(monkeypatch, res)
            state = WalkState()
            action = self._build(
                tmp_path, allow_structural_remedy=True, state=state
            )
            action(_merge_rec(step_ids=(3, 4)))
            _assert_walk_state(state, apply_skip=True)

    def test_merge_session_short_circuit_full_walk_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # rec.id already applied this session → resolved without folding again;
        # apply_skip stays False (a noop resolve), no halt, id set preserved.
        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("merge_bridge must not run on a session hit")

        monkeypatch.setattr("plan_tool.detail.merge_bridge", boom)
        state = WalkState()
        rec = _merge_rec(step_ids=(3, 4))
        state.applied_structural_finding_ids.add(rec.id)
        action = self._build(
            tmp_path, allow_structural_remedy=True, state=state
        )
        result = action(rec)
        assert "already folded" in result
        _assert_walk_state(state, apply_skip=False, applied_ids={rec.id})

    def test_stale_merge_directive_does_not_call_merge_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A saved merge directive whose fingerprint no longer matches the plan
        # on disk (edited/renumbered since it was computed) must NOT fold — its
        # ids may now name different steps. Same freshness rule as re-ground:
        # downgrade to recommend-only, record skip, never call merge_bridge.
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_merge_bridge(monkeypatch, _merge_bridge_result("applied"))
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(_merge_rec(step_ids=(3, 4)))
        assert calls == []  # the bridge is never called — no fold
        assert state.apply_skip is True
        assert "changed since" in result

    def test_merge_empty_saved_fingerprint_does_not_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty saved fingerprint (legacy/unset) carries no staleness info,
        # so the merge guard must not block — merge_bridge is reached normally.
        (tmp_path / "demo.md").write_text("# demo plan\n", encoding="utf-8")
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        action = self._build(
            tmp_path, allow_structural_remedy=True, saved_plan_fingerprint=""
        )
        action(_merge_rec(step_ids=(3, 4)))
        assert len(calls) == 1  # guard skipped, bridge actuated

    def test_matching_signature_merge_actuates_despite_plan_edit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Merge-side mirror of the re-ground fix: an earlier apply changed the
        # whole-plan fingerprint, but this merge directive's OWN targets are
        # untouched, so the stamped signature still matches — it folds instead
        # of downgrading.
        plan = _write_plan_with_steps(
            tmp_path, [(3, "Step 3"), (4, "Step 4")]
        )
        rec = _stamp(_merge_rec(step_ids=(3, 4)), plan)
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("applied")
        )
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_structural_remedy=True,
            saved_plan_fingerprint="whole-plan-fingerprint-that-wont-match",
            state=state,
        )
        result = action(rec)
        assert len(calls) == 1  # bridge reached despite the stale whole-plan fp
        assert state.apply_skip is False  # resolved
        assert "merged steps" in result

    def test_reground_directive_still_routes_to_reground_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The new merge branch must not steal MERGE_ACTION_REGROUND: a re-ground
        # directive still reaches reground_bridge, and merge_bridge is untouched.
        reground_calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        merge_calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert len(reground_calls) == 1
        assert merge_calls == []

    def test_granularity_merge_without_directive_falls_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A granularity-merge finding whose suggested_action carries no
        # directive marker: the bridge is never called and the walk falls to
        # the terminal "run it manually" notice (even though the prose
        # mentions plan-tool merge).
        def boom(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("reground_bridge must not be called")

        monkeypatch.setattr("plan_tool.reground.reground_bridge", boom)
        rec = Recommendation(
            id="granularity-merge-nodirective",
            source="granularity-merge",
            severity="info",
            step_id=None,
            title="adjacent steps fragmented",
            body="steps 3 and 4 are dependent and could merge",
            suggested_action="consider plan-tool merge on steps 3 and 4",
        )
        result = self._build(tmp_path, allow_structural_remedy=True)(rec)
        assert result == _MANUAL_RUN_NOTICE

    def test_is_dispatchable_true_for_directive_finding(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review_walk import is_dispatchable, merge_remedy_target

        rec = _reground_rec(step_ids=(3, 4))
        assert merge_remedy_target(rec) is not None
        assert is_dispatchable(rec) is True

        bare = Recommendation(
            id="gm-bare", source="granularity-merge", severity="info",
            step_id=None, title="t", body="b",
            suggested_action="no directive marker here",
        )
        assert merge_remedy_target(bare) is None
        assert is_dispatchable(bare) is False


# ---------------------------------------------------------------------------
# Step 4: per-remedy opt-ins. ``allow_merge_remedy`` / ``allow_reground_remedy``
# each enable only their own bridge; the umbrella ``allow_structural_remedy``
# still enables both. Each dispatcher's effective opt-in is ``umbrella OR own
# flag``, and all three are forced off under a blanket ``yes_to_all``.
# ---------------------------------------------------------------------------


class TestPerRemedyOptIns:
    """The granular ``--merge`` / ``--reground`` builder kwargs enable exactly
    one bridge without turning the other on."""

    def _build(self, tmp_path: Path, **kwargs):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            **kwargs,
        )

    def test_merge_flag_alone_enables_merge_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        # No umbrella — only the granular merge opt-in.
        action = self._build(tmp_path, allow_merge_remedy=True)
        action(_merge_rec(step_ids=(3, 4)))
        assert calls[0]["allow_merge"] is True

    def test_merge_flag_alone_leaves_reground_recommend_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(tmp_path, allow_merge_remedy=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        # The merge opt-in doesn't leak onto the re-ground bridge.
        assert calls[0]["allow_reground"] is False

    def test_reground_flag_alone_enables_reground_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(tmp_path, allow_reground_remedy=True)
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["allow_reground"] is True

    def test_reground_flag_alone_leaves_merge_recommend_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        action = self._build(tmp_path, allow_reground_remedy=True)
        action(_merge_rec(step_ids=(3, 4)))
        assert calls[0]["allow_merge"] is False

    def test_umbrella_still_enables_both_bridges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        merge_calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        reground_calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        # The umbrella with neither granular flag still means "both on".
        action = self._build(tmp_path, allow_structural_remedy=True)
        action(_merge_rec(step_ids=(3, 4)))
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert merge_calls[0]["allow_merge"] is True
        assert reground_calls[0]["allow_reground"] is True

    def test_merge_flag_forced_off_under_yes_to_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, allow_merge_remedy=True, state=state
        )
        action(_merge_rec(step_ids=(3, 4)))
        # A blanket fast-forward never auto-confirms, granular flag or not.
        assert calls[0]["allow_merge"] is False

    def test_reground_flag_forced_off_under_yes_to_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        state = WalkState(yes_to_all=True)
        action = self._build(
            tmp_path, allow_reground_remedy=True, state=state
        )
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls[0]["allow_reground"] is False

    def test_per_remedy_flags_default_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Neither umbrella nor granular flag: both bridges recommend-only.
        merge_calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("recommended")
        )
        reground_calls = _stub_reground_bridge(
            monkeypatch, _reground_result("recommended")
        )
        action = self._build(tmp_path)
        action(_merge_rec(step_ids=(3, 4)))
        action(_reground_rec(step_ids=(3, 4, 5)))
        assert merge_calls[0]["allow_merge"] is False
        assert reground_calls[0]["allow_reground"] is False

    def test_narrow_merge_flag_still_refuses_stale_saved_directive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A per-remedy opt-in must not widen the mutation surface: the shared
        # stale-directive guard still fires before the opt-in gate, so a stale
        # saved merge directive never reaches the bridge.
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_merge_bridge(
            monkeypatch, _merge_bridge_result("applied")
        )
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_merge_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(_merge_rec(step_ids=(3, 4)))
        assert calls == []  # guard fires before the opt-in gate
        assert state.apply_skip is True
        assert "changed since" in result

    def test_narrow_reground_flag_still_refuses_stale_saved_directive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "demo.md").write_text("# demo plan v2\n", encoding="utf-8")
        calls = _stub_reground_bridge(
            monkeypatch, _reground_result("applied")
        )
        state = WalkState()
        action = self._build(
            tmp_path,
            allow_reground_remedy=True,
            saved_plan_fingerprint="stale-fingerprint-that-wont-match",
            state=state,
        )
        result = action(_reground_rec(step_ids=(3, 4, 5)))
        assert calls == []
        assert state.apply_skip is True
        assert "changed since" in result


_REGROUND_WALK_PLAN = """---
title: Re-ground Walk Integration
status: in-progress
priority: medium
steps:
  - id: 1
    title: First step
    status: current
  - id: 2
    title: Second step
    status: pending
---

# Re-ground Walk Integration
"""


@pytest.mark.integration
class TestRegroundApplyStructuralFlag:
    """The ``--apply-structural`` walk flag flips ``allow_structural_remedy``
    on, and (because the re-ground finding is ``info``-severity) the finding
    is walked only when ``--include-info`` is also passed."""

    def _setup(self, tmp_path: Path):
        import json

        from plan_tool.review_persistence import save_review

        repo = tmp_path
        # Idempotent: the CLI-integration test drives _setup twice (flag on,
        # then off) against the same tmp_path.
        (repo / ".git").mkdir(exist_ok=True)
        plans_dir = repo / "plans"
        plans_dir.mkdir(exist_ok=True)
        plan_rel = "plans/rg.md"
        (repo / plan_rel).write_text(_REGROUND_WALK_PLAN, encoding="utf-8")
        manifest = repo / "m.json"
        manifest.write_text(
            json.dumps({"plans": [plan_rel]}), encoding="utf-8"
        )
        save_review(
            plan_slug="rg",
            plan_path=plan_rel,
            repo_root=repo,
            report_md="reconcile-plan",
            recommendations=[_reground_rec(step_ids=(1, 2))],
        )
        return repo, manifest

    def _drive(self, tmp_path, monkeypatch, extra_flags):
        from plan_tool.cli import app as cli_module
        import plan_tool.cli.review_cmd as review_cmd

        repo, manifest = self._setup(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        build_calls: list[dict] = []
        walk_calls: list[dict] = []

        real_build = review_cmd._build_review_action_fn

        def spy_build(**kwargs):
            build_calls.append(kwargs)
            return real_build(**kwargs)

        def spy_walk(saved, **kwargs):
            walk_calls.append(kwargs)
            return SimpleNamespace(answered=0, quit_early=False)

        monkeypatch.setattr(review_cmd, "_build_review_action_fn", spy_build)
        monkeypatch.setattr(review_cmd, "walk_recommendations", spy_walk)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile-plan-walk", "rg"]
            + extra_flags
        )
        return rc, build_calls, walk_calls

    def test_both_flags_flip_opt_in_and_surface_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rc, build_calls, walk_calls = self._drive(
            tmp_path, monkeypatch, ["--apply-structural", "--include-info"]
        )
        assert rc == 0
        # --apply-structural forwards the opt-in into the action builder …
        assert build_calls
        assert build_calls[-1]["allow_structural_remedy"] is True
        # … and --include-info keeps the info-severity finding in the walk.
        assert walk_calls
        assert walk_calls[-1]["skip_info"] is False

    def test_missing_apply_structural_stays_recommend_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # --include-info surfaces the finding, but without --apply-structural
        # the opt-in stays off → recommend-only.
        rc, build_calls, walk_calls = self._drive(
            tmp_path, monkeypatch, ["--include-info"]
        )
        assert rc == 0
        assert build_calls[-1]["allow_structural_remedy"] is False

    def test_missing_include_info_filters_the_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # --apply-structural opts the walk in, but without --include-info the
        # info-severity finding is filtered out of the dispatch set.
        rc, build_calls, walk_calls = self._drive(
            tmp_path, monkeypatch, ["--apply-structural"]
        )
        assert rc == 0
        assert walk_calls[-1]["skip_info"] is True

    def test_merge_flag_reaches_builder_via_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The granular --merge dest threads through the real argparse → builder
        # path: only allow_merge_remedy flips, allow_reground_remedy stays off.
        rc, build_calls, walk_calls = self._drive(
            tmp_path, monkeypatch, ["--merge"]
        )
        assert rc == 0
        assert build_calls
        assert build_calls[-1]["allow_merge_remedy"] is True
        assert build_calls[-1]["allow_reground_remedy"] is False
        assert build_calls[-1]["allow_structural_remedy"] is False

    def test_reground_flag_reaches_builder_via_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The mirror for --reground: only allow_reground_remedy flips.
        rc, build_calls, walk_calls = self._drive(
            tmp_path, monkeypatch, ["--reground"]
        )
        assert rc == 0
        assert build_calls
        assert build_calls[-1]["allow_reground_remedy"] is True
        assert build_calls[-1]["allow_merge_remedy"] is False
        assert build_calls[-1]["allow_structural_remedy"] is False

    def test_rebaseline_flag_reaches_builder_via_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The --reground-rebaseline dest threads through the real argparse →
        # builder path across the cmd_review_walk call site; the default run
        # (no flag) captures False. Catches a wrong dest or a missed call site
        # the doc-drift guard can't.
        rc, build_calls, _ = self._drive(
            tmp_path, monkeypatch, ["--reground-rebaseline"]
        )
        assert rc == 0
        assert build_calls
        assert build_calls[-1]["reground_rebaseline"] is True

        rc, build_calls, _ = self._drive(tmp_path, monkeypatch, [])
        assert rc == 0
        assert build_calls
        assert build_calls[-1]["reground_rebaseline"] is False


# ---------------------------------------------------------------------------
# File-check create/fix dispatch — the WalkState/apply_skip disposition of each
# ``_dispatch_file_check_create`` outcome (dispatch concern), pinned here.
# ``tests/test_review_walk.py:TestFileCheckCreateDispatch`` owns the orthogonal
# ``files:``→``creates:`` plan-mutation assertions — referenced, not duplicated.
# File-check never halts, never records a structural finding id, and never sets
# apply_failed; the two resolved paths (create / already-declared) leave
# apply_skip False, the three no-op paths (fix / parse-error / step-not-found)
# set it True.
# ---------------------------------------------------------------------------


_FILE_CHECK_PATH = "src/new_module.py"


def _file_check_rec(*, step_id=3, file_path=_FILE_CHECK_PATH):
    """A MISSING_PARENT file-check finding (``file_path`` set) that apply can
    resolve by moving the path from ``files:`` into ``creates:``."""
    return Recommendation(
        id=f"file-check-{step_id}",
        source="file-check",
        severity="medium",
        step_id=step_id,
        title="declared file path doesn't resolve",
        body=f"`{file_path}`'s parent dir doesn't exist",
        suggested_action=None,
        file_path=file_path,
    )


def _write_file_check_plan(tmp_path: Path, *, declare: str) -> None:
    """Write ``demo.md`` with step 3 declaring ``_FILE_CHECK_PATH`` under
    ``declare`` (``"files"`` or ``"creates"``)."""
    (tmp_path / "demo.md").write_text(
        "---\ntitle: Demo\nstatus: in-progress\npriority: medium\nsteps:\n"
        "  - id: 3\n    title: Third step\n    status: pending\n"
        f"    {declare}:\n      - {_FILE_CHECK_PATH}\n"
        "---\n\n# Demo\n",
        encoding="utf-8",
    )


class TestFileCheckCreateWalkState:
    """Pin the full post-call ``WalkState`` for every file-check outcome
    ``action(rec)`` routes to ``_dispatch_file_check_create``."""

    def _build(self, tmp_path: Path, state: WalkState):
        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
        return _build_review_action_fn(
            ctx=ctx, plan_path=tmp_path / "demo.md", plan_name="demo",
            state=state,
        )

    def test_file_check_create_leaves_halt_and_id_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_file_check_plan(tmp_path, declare="files")
        monkeypatch.setattr("builtins.input", lambda *a, **k: "c")
        state = WalkState()
        result = self._build(tmp_path, state)(_file_check_rec())
        assert "moved" in result
        # Resolved (the path moved into creates:) — apply_skip stays False.
        _assert_walk_state(state, apply_skip=False)

    def test_file_check_fix_leaves_halt_and_id_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_file_check_plan(tmp_path, declare="files")
        monkeypatch.setattr("builtins.input", lambda *a, **k: "f")
        state = WalkState()
        result = self._build(tmp_path, state)(_file_check_rec())
        assert "unchanged" in result
        # Nothing moved — apply_skip True, everything else untouched.
        _assert_walk_state(state, apply_skip=True)

    def test_file_check_already_declared_is_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The path is already under creates: (idempotent no-op) — treated as
        # resolved (apply_skip False), NOT a skip, or the finding re-fires
        # forever. The load-bearing minority outcome step 2 must map correctly.
        _write_file_check_plan(tmp_path, declare="creates")
        monkeypatch.setattr("builtins.input", lambda *a, **k: "c")
        state = WalkState()
        result = self._build(tmp_path, state)(_file_check_rec())
        assert "already declared" in result
        _assert_walk_state(state, apply_skip=False)

    def test_file_check_parse_error_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "demo.md").write_text(
            "not a plan: [unterminated\n", encoding="utf-8"
        )
        monkeypatch.setattr("builtins.input", lambda *a, **k: "c")
        state = WalkState()
        result = self._build(tmp_path, state)(_file_check_rec())
        assert "could not read plan" in result
        _assert_walk_state(state, apply_skip=True)

    def test_file_check_step_not_found_sets_apply_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_file_check_plan(tmp_path, declare="files")
        monkeypatch.setattr("builtins.input", lambda *a, **k: "c")
        state = WalkState()
        # step 9 isn't in the plan (only step 3 is).
        result = self._build(tmp_path, state)(_file_check_rec(step_id=9))
        assert "not found" in result
        _assert_walk_state(state, apply_skip=True)


class TestApplyFindingDetailFormatPreflight:
    """One property specific to ``launcher.apply_finding``'s format-version
    preflight, not the routing-table rows the module docstring says are
    pinned elsewhere: an unsupported detail marker must stop the apply
    dispatch before any prompt render or model call, and before any
    mutation — reached here through the real interactive review action,
    not a direct launcher call (see the companion test in
    ``tests/test_launcher.py``)."""

    def test_apply_refuses_unsupported_detail_before_snapshot_or_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import launcher as launcher_module
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        (tmp_path / "demo.md").write_text(
            "---\n"
            "title: Demo\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    detail: detail.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        detail_path = tmp_path / "detail.md"
        detail_path.write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Summary\n\nBody.\n",
            encoding="utf-8",
        )
        original_detail_bytes = detail_path.read_bytes()

        def _must_not_render(*args, **kwargs):
            raise AssertionError(
                "render_prompt must not run before the format-version preflight"
            )

        monkeypatch.setattr(launcher_module, "render_prompt", _must_not_render)

        action = _action_fn(tmp_path)
        rec = Recommendation(
            id="step1-detail-reconcile-format",
            source="detail-reconcile",
            severity="critical",
            step_id=1,
            title="step status should flip",
            body="acceptance criteria not met; flip to current",
            suggested_action=None,
        )

        with pytest.raises(DetailFormatError):
            action(rec)

        assert detail_path.read_bytes() == original_detail_bytes
