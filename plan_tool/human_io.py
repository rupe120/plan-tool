"""Typed human-input providers for interactive command seams."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from plan_tool.fileio import durable_create_text


_HUMAN_IO_MODE_ENV = "PLAN_TOOL_HUMAN_IO"
_HUMAN_IO_DIRECTORY_ENV = "PLAN_TOOL_HUMAN_IO_DIR"
_REMOTE_POLL_INTERVAL_SECONDS = 0.1


class HumanInputError(ValueError):
    """Raised when a human-input request or remote response is invalid."""


@dataclass(frozen=True)
class HumanInputRequest:
    """One prompt the selected provider must present to a human."""

    request_id: str
    prompt_id: str
    prompt: str


@dataclass(frozen=True)
class HumanInputResolution:
    """The text supplied for one matching human-input request."""

    request_id: str
    text: str


HumanInputProvider = Callable[[HumanInputRequest], HumanInputResolution]
TerminalInputFn = Callable[[str], str]


def make_human_input_provider(input_fn: TerminalInputFn) -> HumanInputProvider:
    """Select the terminal or remote provider from the current environment."""
    mode = os.environ.get(_HUMAN_IO_MODE_ENV)
    if mode is None:
        return _make_terminal_provider(input_fn)
    if mode != "remote":
        raise HumanInputError(
            f"unsupported {_HUMAN_IO_MODE_ENV} value {mode!r}; expected 'remote'"
        )

    directory_value = os.environ.get(_HUMAN_IO_DIRECTORY_ENV)
    if not directory_value:
        raise HumanInputError(
            f"{_HUMAN_IO_DIRECTORY_ENV} must name an existing usable directory"
        )
    directory = Path(directory_value)
    _validate_remote_directory(directory)
    return _make_remote_provider(directory)


def _make_terminal_provider(input_fn: TerminalInputFn) -> HumanInputProvider:
    def provide(request: HumanInputRequest) -> HumanInputResolution:
        return HumanInputResolution(request_id=request.request_id, text=input_fn(request.prompt))

    return provide


def _make_remote_provider(directory: Path) -> HumanInputProvider:
    def provide(request: HumanInputRequest) -> HumanInputResolution:
        _validate_request(request)
        request_path, resolution_path = _record_paths(directory, request.request_id)
        if resolution_path.exists():
            raise HumanInputError(
                f"human-input resolution record already exists: {resolution_path}"
            )

        try:
            durable_create_text(request_path, _serialize_request(request))
        except FileExistsError as exc:
            raise HumanInputError(
                f"human-input request record already exists: {request_path}"
            ) from exc
        while not resolution_path.exists():
            time.sleep(_REMOTE_POLL_INTERVAL_SECONDS)
        return _read_resolution(resolution_path, request.request_id)

    return provide


def _validate_remote_directory(directory: Path) -> None:
    try:
        is_directory = directory.is_dir()
        is_usable = os.access(directory, os.R_OK | os.W_OK | os.X_OK)
    except OSError as exc:
        raise HumanInputError(f"cannot use human-input remote directory {directory}: {exc}") from exc
    if not is_directory:
        raise HumanInputError(
            f"{_HUMAN_IO_DIRECTORY_ENV} must name an existing directory: {directory}"
        )
    if not is_usable:
        raise HumanInputError(
            f"{_HUMAN_IO_DIRECTORY_ENV} must be readable and writable: {directory}"
        )


def _validate_request(request: HumanInputRequest) -> None:
    if not isinstance(request.request_id, str):
        raise HumanInputError("human-input request id must be text")
    _validate_request_id(request.request_id)
    if not isinstance(request.prompt_id, str):
        raise HumanInputError("human-input prompt id must be text")
    if not isinstance(request.prompt, str):
        raise HumanInputError("human-input prompt must be text")


def _validate_request_id(request_id: str) -> None:
    if (
        not request_id
        or request_id in {".", ".."}
        or "\x00" in request_id
        or any(separator in request_id for separator in ("/", "\\"))
    ):
        raise HumanInputError("human-input request id must be one safe filename component")


def _record_paths(directory: Path, request_id: str) -> tuple[Path, Path]:
    return (
        directory / f"{request_id}.request.json",
        directory / f"{request_id}.resolution.json",
    )


def _serialize_request(request: HumanInputRequest) -> str:
    return json.dumps(
        {
            "request_id": request.request_id,
            "prompt_id": request.prompt_id,
            "prompt": request.prompt,
        },
        sort_keys=True,
    ) + "\n"


def _read_resolution(path: Path, request_id: str) -> HumanInputResolution:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanInputError(f"invalid human-input resolution record {path}: {exc}") from exc
    if not isinstance(record, dict):
        raise HumanInputError(f"invalid human-input resolution record {path}: expected an object")

    resolved_request_id = record.get("request_id")
    text = record.get("text")
    if not isinstance(resolved_request_id, str) or not isinstance(text, str):
        raise HumanInputError(
            f"invalid human-input resolution record {path}: expected request_id and text"
        )
    if resolved_request_id != request_id:
        raise HumanInputError(
            f"human-input resolution record {path} belongs to {resolved_request_id!r}, "
            f"not {request_id!r}"
        )
    return HumanInputResolution(request_id=resolved_request_id, text=text)
