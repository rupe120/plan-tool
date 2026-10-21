from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool import human_io
from plan_tool.fileio import durable_create_text
from plan_tool.human_io import (
    HumanInputError,
    HumanInputRequest,
    HumanInputResolution,
    make_human_input_provider,
)


def _request(request_id: str = "request-1") -> HumanInputRequest:
    return HumanInputRequest(
        request_id=request_id,
        prompt_id="review-annotation",
        prompt="Choose an action: ",
    )


def _configure_remote(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(directory))


def _record_paths(directory: Path, request: HumanInputRequest) -> tuple[Path, Path]:
    return (
        directory / f"{request.request_id}.request.json",
        directory / f"{request.request_id}.resolution.json",
    )


def _publish_resolution(path: Path, request_id: str, text: str) -> None:
    durable_create_text(
        path,
        json.dumps({"request_id": request_id, "text": text}) + "\n",
    )


def test_terminal_provider_forwards_the_exact_prompt_to_input_fn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
    prompts: list[str] = []
    provider = make_human_input_provider(lambda prompt: prompts.append(prompt) or "answer\n")

    resolution = provider(_request())

    assert prompts == ["Choose an action: "]
    assert resolution == HumanInputResolution(request_id="request-1", text="answer\n")


def test_remote_mode_requires_an_existing_usable_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
    monkeypatch.delenv("PLAN_TOOL_HUMAN_IO_DIR", raising=False)
    with pytest.raises(HumanInputError, match="existing usable directory"):
        make_human_input_provider(input)

    _configure_remote(monkeypatch, tmp_path / "missing")
    with pytest.raises(HumanInputError, match="existing directory"):
        make_human_input_provider(input)

    not_a_directory = tmp_path / "record.json"
    not_a_directory.write_text("{}\n", encoding="utf-8")
    _configure_remote(monkeypatch, not_a_directory)
    with pytest.raises(HumanInputError, match="existing directory"):
        make_human_input_provider(input)

    _configure_remote(monkeypatch, tmp_path)
    monkeypatch.setattr(human_io.os, "access", lambda *args: False)
    with pytest.raises(HumanInputError, match="readable and writable"):
        make_human_input_provider(input)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["record.json"]


def test_unknown_human_io_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "webhook")

    with pytest.raises(HumanInputError, match="unsupported PLAN_TOOL_HUMAN_IO"):
        make_human_input_provider(input)


def test_provider_mode_is_fixed_when_constructed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    monkeypatch.delenv("PLAN_TOOL_HUMAN_IO")
    monkeypatch.delenv("PLAN_TOOL_HUMAN_IO_DIR")
    request_path, resolution_path = _record_paths(tmp_path, request)

    def publish_after_request(_: float) -> None:
        assert request_path.exists()
        _publish_resolution(resolution_path, request.request_id, "remote answer")

    monkeypatch.setattr(human_io.time, "sleep", publish_after_request)

    assert provider(request) == HumanInputResolution(request.request_id, "remote answer")


def test_remote_request_record_preserves_request_identity_and_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, resolution_path = _record_paths(tmp_path, request)

    def publish_after_request(_: float) -> None:
        _publish_resolution(resolution_path, request.request_id, "done")

    monkeypatch.setattr(human_io.time, "sleep", publish_after_request)

    provider(request)

    assert json.loads(request_path.read_text(encoding="utf-8")) == {
        "request_id": "request-1",
        "prompt_id": "review-annotation",
        "prompt": "Choose an action: ",
    }


def test_remote_waits_for_matching_text_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, resolution_path = _record_paths(tmp_path, request)
    waits: list[float] = []

    def publish_after_wait(interval: float) -> None:
        waits.append(interval)
        assert request_path.exists()
        _publish_resolution(resolution_path, request.request_id, "operator answer")

    monkeypatch.setattr(human_io.time, "sleep", publish_after_wait)

    assert provider(request) == HumanInputResolution(request.request_id, "operator answer")
    assert waits == [human_io._REMOTE_POLL_INTERVAL_SECONDS]


def test_remote_ignores_in_progress_resolution_until_complete_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    _, resolution_path = _record_paths(tmp_path, request)
    temporary_path = resolution_path.with_name(f".{resolution_path.name}.writing")
    waits = 0

    def publish_in_stages(_: float) -> None:
        nonlocal waits
        waits += 1
        if waits == 1:
            temporary_path.write_text("not a final record", encoding="utf-8")
        else:
            _publish_resolution(resolution_path, request.request_id, "complete answer")

    monkeypatch.setattr(human_io.time, "sleep", publish_in_stages)

    assert provider(request) == HumanInputResolution(request.request_id, "complete answer")
    assert waits == 2
    assert temporary_path.read_text(encoding="utf-8") == "not a final record"


@pytest.mark.parametrize(
    "resolution_text",
    [
        "{not JSON}\n",
        json.dumps({"request_id": "request-1"}) + "\n",
    ],
    ids=["invalid-json", "missing-text"],
)
def test_remote_rejects_malformed_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolution_text: str,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, resolution_path = _record_paths(tmp_path, request)

    def publish_invalid_resolution(_: float) -> None:
        durable_create_text(resolution_path, resolution_text)

    monkeypatch.setattr(human_io.time, "sleep", publish_invalid_resolution)

    with pytest.raises(HumanInputError, match="invalid human-input resolution"):
        provider(request)

    assert request_path.exists()
    assert resolution_path.read_text(encoding="utf-8") == resolution_text


def test_remote_rejects_mismatched_resolution_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, resolution_path = _record_paths(tmp_path, request)

    def publish_other_request_resolution(_: float) -> None:
        _publish_resolution(resolution_path, "request-2", "wrong request")

    monkeypatch.setattr(human_io.time, "sleep", publish_other_request_resolution)

    with pytest.raises(HumanInputError, match="belongs to 'request-2'"):
        provider(request)

    assert request_path.exists()
    assert json.loads(resolution_path.read_text(encoding="utf-8"))["request_id"] == "request-2"


def test_existing_request_record_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, _ = _record_paths(tmp_path, request)
    request_path.write_text("existing request\n", encoding="utf-8")

    with pytest.raises(HumanInputError, match="request record already exists"):
        provider(request)

    assert request_path.read_text(encoding="utf-8") == "existing request\n"


def test_existing_resolution_record_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request_path, resolution_path = _record_paths(tmp_path, request)
    resolution_path.write_text("existing resolution\n", encoding="utf-8")

    with pytest.raises(HumanInputError, match="resolution record already exists"):
        provider(request)

    assert not request_path.exists()
    assert resolution_path.read_text(encoding="utf-8") == "existing resolution\n"


def test_request_id_cannot_escape_the_remote_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_remote(monkeypatch, tmp_path)
    provider = make_human_input_provider(input)
    request = _request("../outside")

    with pytest.raises(HumanInputError, match="safe filename component"):
        provider(request)

    assert not (tmp_path.parent / "outside.request.json").exists()
    assert list(tmp_path.iterdir()) == []
