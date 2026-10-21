from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import plan_tool.cli as cli
import plan_tool.cli.app as app
from plan_tool import data_contract as contract
from plan_tool.cli import data_contract_cmd
from plan_tool.review import Recommendation
from plan_tool.review_persistence import Annotation, load_review, save_review


def _rec(
    rec_id: str,
    *,
    source: str = "data-contract",
    title: str = "contract drift",
    anchor: str | None = None,
    confidence: str | None = "limited",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source=source,
        severity="medium",
        step_id=None,
        title=title,
        body=title,
        suggested_action="Update DATA_CONTRACT.md.",
        anchor=anchor,
        confidence=confidence,
    )


def _write_payloads(saved_path: Path, payloads: dict[str, dict]) -> Path:
    path = saved_path.with_name(f"{saved_path.stem}-data-contract.json")
    path.write_text(
        json.dumps(
            {
                "kind": "data-contract",
                "review_id": saved_path.stem,
                "payloads": payloads,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _contract_text() -> str:
    return (
        "# Application Data Contract\n\n"
        "## Saved review sidecar\n\n"
        "### `SavedReview` (`review_persistence.py`)\n\n"
        "| Field | Persisted | Meaning |\n"
        "|---|---|---|\n"
        "| `plan_slug` | yes | slug |\n"
    )


def _payload(repo_root: Path, *, operation: str = "add", target: str = "DATA_CONTRACT.md") -> dict:
    text = (repo_root / "DATA_CONTRACT.md").read_text(encoding="utf-8")
    return {
        "target": target,
        "source_type": "dataclass",
        "owner": "SavedReview",
        "field_or_key": "created_at",
        "target_section": "SavedReview",
        "operation": operation,
        "candidate_fields": {
            "source_symbol": "plan_tool/review_persistence.py:SavedReview",
            "field": "created_at",
            "json_key": "created_at",
        },
        "freshness": {
            "registry_fingerprint": contract.registry_fingerprint(),
            "contract_fingerprint": contract.contract_fingerprint(text),
        },
    }


def _save_completeness(
    tmp_repo,
    recs: list[Recommendation],
    payloads: dict[str, dict],
    *,
    kind: str = "completeness",
    when: datetime = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
) -> Path:
    plan_path = tmp_repo.plans[0]
    from plan_tool.review_persistence import AuditInputSnapshot

    snapshot = AuditInputSnapshot.capture(plan_path, tmp_repo.root)
    save_kwargs = dict(
        plan_slug="demo",
        plan_path=str(plan_path.relative_to(tmp_repo.root)),
        repo_root=tmp_repo.root,
        report_md="report",
        recommendations=recs,
        kind=kind,
        now=when,
    )
    if kind == "completeness":
        save_kwargs["qualified_result"] = {
            "headline": "awaiting-human-action",
            "stage": "detail",
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        }
    saved_path = save_review(**save_kwargs)
    _write_payloads(saved_path, payloads)
    return saved_path


def _args(tmp_repo, *extra: str) -> argparse.Namespace:
    return cli.build_parser().parse_args(
        tmp_repo.argv("data-contract-apply", "demo", *extra)
    )


def test_registers_data_contract_apply_command() -> None:
    parser = cli.build_parser()
    commands = {
        choice
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
        for choice in action.choices
    }
    assert "data-contract-apply" in commands
    _, dispatch = cli.app.assemble(app.__doc__, app.COMMAND_MODULES)
    assert dispatch["data-contract-apply"] is data_contract_cmd.cmd_data_contract_apply


def test_data_contract_apply_is_locked_mutating_command() -> None:
    assert "data-contract-apply" in app._LOCKED_MUTATING_COMMANDS


def test_finding_label_renders_stored_legacy_confidence() -> None:
    assert "confidence: unknown" in data_contract_cmd._finding_label(
        _rec("dc-legacy", confidence=None)
    )


def test_errors_when_no_completeness_audit_exists(registered_plan, capsys) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")

    rc = data_contract_cmd.cmd_data_contract_apply(_args(registered_plan))

    assert rc == 2
    assert "completeness-audit" in capsys.readouterr().err


def test_errors_on_non_completeness_save(registered_plan, capsys) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    saved_path = _save_completeness(
        registered_plan,
        [rec],
        {"dc-1": _payload(registered_plan.root)},
        kind="review",
    )

    rc = data_contract_cmd.cmd_data_contract_apply(
        _args(registered_plan, "--id", saved_path.stem)
    )

    assert rc == 2
    assert "not a completeness audit" in capsys.readouterr().err


def test_explicit_legacy_completeness_sidecar_requires_fresh_audit(
    registered_plan, capsys
) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(
        _contract_text(), encoding="utf-8"
    )
    path = save_review(
        plan_slug="demo",
        plan_path=registered_plan.plans[0].relative_to(registered_plan.root).as_posix(),
        repo_root=registered_plan.root,
        report_md="report",
        recommendations=[_rec("dc-1")],
        kind="completeness",
    )
    # Eligibility must be checked before a sibling payload is decoded: the
    # sidecar is already legacy/ineligible, so malformed payload bytes must
    # not replace the required fresh-audit route with a payload parse error.
    path.with_name(f"{path.stem}-data-contract.json").write_text(
        "{not json", encoding="utf-8"
    )

    assert data_contract_cmd.cmd_data_contract_apply(
        _args(registered_plan, "--id", path.stem)
    ) == 2
    err = capsys.readouterr().err
    assert "completeness-audit demo" in err
    assert "could not read" not in err


def test_filters_saved_review_to_applyable_contract_doc_findings(
    registered_plan, monkeypatch
) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    applyable = _rec("dc-1")
    other = _rec("other-1", source="plan-completeness")
    non_doc = _rec("dc-2", title="input reference")
    _save_completeness(
        registered_plan,
        [other, applyable, non_doc],
        {
            "dc-1": _payload(registered_plan.root),
            "dc-2": _payload(registered_plan.root, target="plans/1-demo.md"),
        },
    )
    seen: list[str] = []

    class _TTY:
        def isatty(self) -> bool:
            return True

    def fake_walk(saved, **kwargs):
        seen.extend(rec.id for rec in saved.recommendations)
        return argparse.Namespace(answered=0)

    monkeypatch.setattr(data_contract_cmd.sys, "stdin", _TTY())
    monkeypatch.setattr(data_contract_cmd, "walk_recommendations", fake_walk)

    assert data_contract_cmd.cmd_data_contract_apply(_args(registered_plan)) == 0
    assert seen == ["dc-1"]


def test_input_reference_findings_are_reported_non_applyable(
    registered_plan, monkeypatch, capsys
) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    input_ref = _rec("dc-input", title="stale ## Input reference")
    _save_completeness(
        registered_plan,
        [input_ref],
        {"dc-input": _payload(registered_plan.root, target="plans/1-demo.md")},
    )

    class _TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(data_contract_cmd.sys, "stdin", _TTY())

    rc = data_contract_cmd.cmd_data_contract_apply(_args(registered_plan))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Skipping non-applyable" in out
    assert "DATA_CONTRACT.md" in out


def test_anchor_filters_by_id_or_anchor(registered_plan, monkeypatch) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    first = _rec("dc-1", anchor="first-anchor")
    second = _rec("dc-2", anchor="second-anchor")
    _save_completeness(
        registered_plan,
        [first, second],
        {
            "dc-1": _payload(registered_plan.root),
            "dc-2": _payload(registered_plan.root),
        },
    )
    seen: list[str] = []

    class _TTY:
        def isatty(self) -> bool:
            return True

    def fake_walk(saved, **kwargs):
        seen.extend(rec.id for rec in saved.recommendations)
        return argparse.Namespace(answered=0)

    monkeypatch.setattr(data_contract_cmd.sys, "stdin", _TTY())
    monkeypatch.setattr(data_contract_cmd, "walk_recommendations", fake_walk)

    assert (
        data_contract_cmd.cmd_data_contract_apply(
            _args(registered_plan, "--anchor", "second-anchor")
        )
        == 0
    )
    assert seen == ["dc-2"]


def test_non_interactive_reports_without_walking(
    registered_plan, monkeypatch, capsys
) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    _save_completeness(
        registered_plan,
        [rec],
        {"dc-1": _payload(registered_plan.root)},
    )

    def fail_walk(*args, **kwargs):
        raise AssertionError("walk should not run")

    monkeypatch.setattr(data_contract_cmd, "walk_recommendations", fail_walk)

    assert data_contract_cmd.cmd_data_contract_apply(_args(registered_plan)) == 0
    out = capsys.readouterr().out
    assert "dc-1" in out


def test_walk_persists_annotations_to_saved_audit(registered_plan, monkeypatch) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    saved_path = _save_completeness(
        registered_plan,
        [rec],
        {"dc-1": _payload(registered_plan.root)},
    )

    class _TTY:
        def isatty(self) -> bool:
            return True

    def fake_walk(saved, **kwargs):
        persist = kwargs.get("persist_fn")
        if persist is None:
            from plan_tool.review_persistence import update_annotation as persist

        persist(saved.path, "dc-1", Annotation("skip", "later"))
        return argparse.Namespace(answered=1)

    monkeypatch.setattr(data_contract_cmd.sys, "stdin", _TTY())
    monkeypatch.setattr(data_contract_cmd, "walk_recommendations", fake_walk)

    assert data_contract_cmd.cmd_data_contract_apply(_args(registered_plan)) == 0
    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert data["annotations"]["dc-1"]["status"] == "skip"
    assert "detail_bundle_fingerprint_present" in data


def test_apply_dispatch_updates_data_contract_for_data_contract_rec(
    registered_plan,
) -> None:
    doc = registered_plan.root / "DATA_CONTRACT.md"
    doc.write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    saved_path = _save_completeness(
        registered_plan,
        [rec],
        {"dc-1": _payload(registered_plan.root)},
    )
    saved = load_review(saved_path)
    payloads = data_contract_cmd._load_payloads(saved_path)
    state = data_contract_cmd.WalkState()
    action = data_contract_cmd._make_action_fn(
        payloads=payloads,
        repo_root=registered_plan.root,
        state=state,
    )

    msg = action(saved.recommendations[0])

    assert msg == "updated DATA_CONTRACT.md"
    assert "`created_at`" in doc.read_text(encoding="utf-8")


def test_apply_requires_structured_payload(registered_plan) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    state = data_contract_cmd.WalkState()
    action = data_contract_cmd._make_action_fn(
        payloads={},
        repo_root=registered_plan.root,
        state=state,
    )

    msg = action(rec)

    assert state.apply_skip is True
    assert "missing applyable data-contract payload" in msg


def test_apply_does_not_apply_input_reference_findings(registered_plan) -> None:
    doc = registered_plan.root / "DATA_CONTRACT.md"
    doc.write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-input", title="stale ## Input reference")
    payload = _payload(registered_plan.root, target="plan-detail")
    payload["operation"] = "validate-input-reference"
    payload["location"] = "details/01.md:## Input"
    state = data_contract_cmd.WalkState()
    action = data_contract_cmd._make_action_fn(
        payloads={"dc-input": payload},
        repo_root=registered_plan.root,
        state=state,
    )

    msg = action(rec)

    assert state.apply_skip is True
    assert "missing applyable data-contract payload" in msg
    assert "`created_at`" not in doc.read_text(encoding="utf-8")


def test_apply_refuses_stale_fingerprints(registered_plan) -> None:
    doc = registered_plan.root / "DATA_CONTRACT.md"
    doc.write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    payload = _payload(registered_plan.root)
    payload["freshness"]["contract_fingerprint"] = "stale"
    state = data_contract_cmd.WalkState()
    action = data_contract_cmd._make_action_fn(
        payloads={"dc-1": payload},
        repo_root=registered_plan.root,
        state=state,
    )

    msg = action(rec)

    assert state.apply_skip is True
    assert "rerun `plan-tool completeness-audit`" in msg
    assert "`created_at`" not in doc.read_text(encoding="utf-8")


def test_failed_apply_records_failed_annotation(registered_plan, monkeypatch) -> None:
    (registered_plan.root / "DATA_CONTRACT.md").write_text(_contract_text(), encoding="utf-8")
    rec = _rec("dc-1")
    payload = _payload(registered_plan.root)
    state = data_contract_cmd.WalkState()
    action = data_contract_cmd._make_action_fn(
        payloads={"dc-1": payload},
        repo_root=registered_plan.root,
        state=state,
    )
    monkeypatch.setattr(
        data_contract_cmd,
        "_apply_payload_to_contract",
        lambda path, payload: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    msg = action(rec)

    assert state.apply_failed is True
    assert msg == "failed: boom"


def test_in_memory_only_row_reads_not_persisted_and_preserves_meaning() -> None:
    text = (
        "# Contract\n\n"
        "### `SavedReview` (`review_persistence.py`)\n\n"
        "| Field | Persisted | Meaning |\n"
        "|---|---|---|\n"
        "| `path` | yes | file path set by load_review |\n"
    )
    payload = {
        "operation": "update",
        "target_section": "SavedReview",
        "field_or_key": "path",
        "candidate_fields": {"field": "path", "requirement": "in_memory_only"},
    }

    updated = data_contract_cmd._apply_add_or_update(text, payload)

    # Persisted column reads not-persisted; the operator meaning survives.
    assert "| `path` | **no** (in-memory) | file path set by load_review |" in updated
    # The collector's in-memory drift condition is satisfied → converges.
    assert "`path`" in updated and "in-memory" in updated.lower()


def test_alias_update_preserves_meaning_and_shows_json_key() -> None:
    text = (
        "### `SavedReview` (`review_persistence.py`)\n\n"
        "| Field | Persisted | Meaning |\n"
        "|---|---|---|\n"
        "| `schema_version` | yes | schema version int |\n"
    )
    payload = {
        "operation": "update",
        "target_section": "SavedReview",
        "field_or_key": "version",
        "candidate_fields": {
            "field": "schema_version",
            "json_key": "version",
            "requirement": "json_key_alias",
        },
    }

    updated = data_contract_cmd._apply_add_or_update(text, payload)

    assert (
        "| `schema_version` | yes (as JSON `version`) | schema version int |"
        in updated
    )


def test_section_bounds_prefers_backticked_owner_token() -> None:
    # A bare-substring match would resolve the "Recommendations" heading first;
    # the backtick-anchored match must find the real `Recommendation` section.
    text = (
        "## Recommendations overview\n\nprose\n\n"
        "### `Recommendation` (`review.py`)\n\n"
        "| Field | Persisted | Meaning |\n|---|---|---|\n"
        "| `id` | yes | rec id |\n"
    )
    bounds = data_contract_cmd._section_bounds(text, "Recommendation")
    assert bounds is not None
    start, end = bounds
    assert text[start:end].startswith("### `Recommendation`")
