"""The selected model's context window for the prompt-budget advisory."""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import threading
from pathlib import Path

import pytest

from plan_tool import context_window, prompt_budget
from plan_tool.backend import (
    CLAUDE_BACKEND,
    CODEX_BACKEND,
    observe_context_window,
    scoped_active_backend,
)
from plan_tool.context_window import active_context_window, context_window_for


def _codex_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    models: list[dict] | None = None,
    config: str | None = 'model = "gpt-6.1-sol"\n',
) -> Path:
    home = tmp_path / "codex-home"
    home.mkdir()
    if models is not None:
        (home / "models_cache.json").write_text(json.dumps({"models": models}), encoding="utf-8")
    if config is not None:
        (home / "config.toml").write_text(config, encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


_SOL = {"slug": "gpt-6.1-sol", "context_window": 272_000, "effective_context_window_percent": 95}


# --- Codex's local catalog ---------------------------------------------------


def test_codex_window_is_the_usable_share_of_the_catalog_window(tmp_path, monkeypatch) -> None:
    """Codex compacts at `effective_context_window_percent`, so that share is the budget."""
    _codex_home(tmp_path, monkeypatch, models=[_SOL])

    assert context_window_for("codex", "gpt-6.1-sol") == 272_000 * 95 // 100


def test_the_default_codex_home_is_dot_codex_under_the_home_directory(tmp_path, monkeypatch) -> None:
    """Most Codex users never set `CODEX_HOME`; an unset or empty one means `~/.codex`."""
    home = tmp_path / "user-home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "models_cache.json").write_text(json.dumps({"models": [_SOL]}), encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert context_window_for("codex", "gpt-6.1-sol") == 258_400
    monkeypatch.setenv("CODEX_HOME", "")
    assert context_window_for("codex", "gpt-6.1-sol") == 258_400


def test_an_explicit_model_outranks_the_one_in_the_codex_config(tmp_path, monkeypatch) -> None:
    """`--model` decides which window applies; `config.toml`'s model is only the fallback."""
    _codex_home(
        tmp_path, monkeypatch,
        models=[{**_SOL, "slug": "small", "context_window": 100_000}, _SOL],
        config='model = "small"\n',
    )

    assert context_window_for("codex", "gpt-6.1-sol") == 258_400
    assert context_window_for("codex", None) == 95_000


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"slug": "m", "context_window": 272_000}, 272_000),                                   # no percent key: the whole window
        ({"slug": "m", "context_window": 272_000, "effective_context_window_percent": 100}, 272_000),
        ({"slug": "m", "context_window": 272_000, "effective_context_window_percent": 101}, 272_000),
        ({"slug": "m", "context_window": 272_000, "effective_context_window_percent": True}, 272_000),
    ],
)
def test_the_effective_percent_defaults_to_the_whole_window_when_absent_or_out_of_range(
    tmp_path, monkeypatch, entry, expected
) -> None:
    _codex_home(tmp_path, monkeypatch, models=[entry])

    assert context_window_for("codex", "m") == expected


# A trimmed copy of what each CLI emitted on 2026-10-09 (see docs/reference/contracts/model-window-sources.md).
_REAL_CODEX_ENTRY = {
    "slug": "gpt-6.1-sol",
    "context_window": 272000,
    "max_context_window": 872000,
    "effective_context_window_percent": 95,
    "supports_experimental_context": False,
    "experimental_supported_tools": ["send_user_message_async", "clock"],
}


def test_a_recorded_real_codex_catalog_entry_yields_its_usable_window(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_REAL_CODEX_ENTRY])

    assert context_window_for("codex", "gpt-6.1-sol") == 258_400


def test_codex_without_a_model_flag_uses_the_model_in_its_config(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_SOL, {**_SOL, "slug": "other", "context_window": 1}])

    assert context_window_for("codex", None) == 258_400


@pytest.mark.parametrize(
    "case",
    ["no-cache-file", "unknown-model", "malformed-cache", "cache-is-a-list", "no-config-model", "bad-window"],
)
def test_codex_window_unknown_inputs_mean_not_known_and_never_raise(tmp_path, monkeypatch, case) -> None:
    if case == "no-cache-file":
        _codex_home(tmp_path, monkeypatch)
    elif case == "unknown-model":
        _codex_home(tmp_path, monkeypatch, models=[{**_SOL, "slug": "someone-else"}])
    elif case == "malformed-cache":
        home = _codex_home(tmp_path, monkeypatch)
        (home / "models_cache.json").write_text("{not json", encoding="utf-8")
    elif case == "cache-is-a-list":
        home = _codex_home(tmp_path, monkeypatch)
        (home / "models_cache.json").write_text("[]", encoding="utf-8")
    elif case == "no-config-model":
        _codex_home(tmp_path, monkeypatch, models=[_SOL], config="")
    else:
        _codex_home(tmp_path, monkeypatch, models=[{**_SOL, "context_window": True}])

    assert context_window_for("codex", "gpt-6.1-sol" if case != "no-config-model" else None) is None


def test_codex_out_of_range_percent_falls_back_to_the_whole_window(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[{**_SOL, "effective_context_window_percent": 0}])

    assert context_window_for("codex", "gpt-6.1-sol") == 272_000


def test_only_codex_reads_the_codex_catalog(tmp_path, monkeypatch) -> None:
    """A Claude model sharing a slug with a Codex entry must not borrow its window."""
    _codex_home(tmp_path, monkeypatch, models=[_SOL])

    assert context_window_for("claude", "gpt-6.1-sol") is None
    assert context_window_for("cursor", "gpt-6.1-sol") is None


def test_a_refusal_gate_can_exclude_observed_windows_but_keeps_the_codex_catalog(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    observe_context_window("codex", "gpt-6.1-sol", 500_000)
    observe_context_window("claude", None, 1_000_000)

    assert context_window_for("codex", "gpt-6.1-sol", observed=False) == 258_400
    assert context_window_for("claude", None, observed=False) is None
    assert context_window_for("codex", "gpt-6.1-sol") == 500_000


@pytest.mark.parametrize("models", [None, 5, "x", {"a": 1}, [None, 3, {"slug": 4}]])
def test_a_catalog_whose_models_are_not_a_list_of_entries_is_not_known_and_never_raises(
    tmp_path, monkeypatch, models
) -> None:
    home = _codex_home(tmp_path, monkeypatch)
    (home / "models_cache.json").write_text(json.dumps({"models": models}), encoding="utf-8")

    assert context_window_for("codex", "gpt-6.1-sol") is None


def test_the_lookup_never_raises_when_the_home_directory_cannot_be_resolved(monkeypatch) -> None:
    def no_home(cls):
        raise RuntimeError("no home")

    monkeypatch.setattr(Path, "home", classmethod(no_home))

    assert context_window_for("codex", "gpt-6.1-sol") is None


def test_the_active_lookup_never_raises_even_when_resolution_does(monkeypatch) -> None:
    def boom():
        raise RuntimeError("no backend")

    monkeypatch.setattr(context_window, "get_active_backend", boom)

    assert active_context_window() is None


def _count_calls(monkeypatch, name: str) -> list[int]:
    """Count calls to one of this module's own parse functions: a process-wide patch of `json.loads`
    would also count unrelated callers on other threads and make the assertions flaky."""
    monkeypatch.setattr(context_window, "_FILE_MEMO", {})
    calls: list[int] = []
    real = getattr(context_window, name)

    def counting(path):
        calls.append(1)
        return real(path)

    monkeypatch.setattr(context_window, name, counting)
    return calls


def _count_parses(monkeypatch) -> list[int]:
    return _count_calls(monkeypatch, "_parse_codex_catalog")


def test_the_codex_catalog_is_parsed_once_per_file_version(tmp_path, monkeypatch) -> None:
    """The cache embeds every model's instructions and is read by every budget check."""
    home = _codex_home(tmp_path, monkeypatch, models=[_SOL])
    parses = _count_parses(monkeypatch)

    assert [context_window_for("codex", "gpt-6.1-sol") for _ in range(5)] == [258_400] * 5
    assert len(parses) == 1

    # A different SIZE is a new version regardless of the filesystem's timestamp granularity.
    (home / "models_cache.json").write_text(
        json.dumps({"models": [{**_SOL, "context_window": 100_000, "padding": "x" * 64}]}), encoding="utf-8"
    )

    assert context_window_for("codex", "gpt-6.1-sol") == 95_000
    assert len(parses) == 2


def test_a_same_size_rewrite_is_a_new_version_when_the_modification_time_changes(tmp_path, monkeypatch) -> None:
    """Pins the mtime component without relying on the clock: the body keeps its length and the
    timestamp is set explicitly."""
    home = _codex_home(tmp_path, monkeypatch, models=[_SOL])
    cache = home / "models_cache.json"
    parses = _count_parses(monkeypatch)
    assert context_window_for("codex", "gpt-6.1-sol") == 258_400
    first = cache.stat()

    cache.write_text(json.dumps({"models": [{**_SOL, "context_window": 100000}]}), encoding="utf-8")
    assert cache.stat().st_size == first.st_size
    os.utime(cache, ns=(first.st_atime_ns, first.st_mtime_ns + 5_000_000_000))

    assert context_window_for("codex", "gpt-6.1-sol") == 95_000
    assert len(parses) == 2


def test_concurrent_cold_lookups_all_get_the_catalog_window_and_parse_once(tmp_path, monkeypatch) -> None:
    """`detail --jobs N` resolves windows from worker threads; a miss must never read as "unknown"."""
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    parses = _count_parses(monkeypatch)
    results: list[object] = []
    gate = threading.Barrier(8)

    def lookup() -> None:
        gate.wait()
        results.append(context_window_for("codex", "gpt-6.1-sol"))

    threads = [threading.Thread(target=lookup) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == [258_400] * 8
    assert len(parses) == 1


def test_an_unreadable_catalog_is_parsed_once_per_version_not_on_every_lookup(tmp_path, monkeypatch) -> None:
    home = _codex_home(tmp_path, monkeypatch)
    (home / "models_cache.json").write_text("{not json", encoding="utf-8")
    parses = _count_parses(monkeypatch)

    assert [context_window_for("codex", "gpt-6.1-sol") for _ in range(4)] == [None] * 4
    assert len(parses) == 1

    (home / "models_cache.json").write_text(json.dumps({"models": [_SOL]}), encoding="utf-8")

    assert context_window_for("codex", "gpt-6.1-sol") == 258_400


def test_a_transient_read_error_is_not_cached_as_an_unreadable_file(tmp_path, monkeypatch) -> None:
    """A descriptor limit or a momentary permission error leaves the file's version unchanged, so
    caching it would pin the default window for the rest of the process."""
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    monkeypatch.setattr(context_window, "_FILE_MEMO", {})
    real = Path.read_text
    failures = [OSError("too many open files")]

    def flaky(self, *args, **kwargs):
        if self.name == "models_cache.json" and failures:
            raise failures.pop()
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)

    assert context_window_for("codex", "gpt-6.1-sol") is None  # this lookup only
    assert context_window_for("codex", "gpt-6.1-sol") == 258_400


def test_a_same_size_same_tick_replacement_by_rename_is_a_new_version(tmp_path, monkeypatch) -> None:
    """The inode is what tells a refresh that renames a new file over the old one, with equal size and
    modification time, from the file already parsed. (`st_dev` cannot be varied in a unit test.)"""
    home = _codex_home(tmp_path, monkeypatch, models=[_SOL])
    cache = home / "models_cache.json"
    parses = _count_parses(monkeypatch)
    assert context_window_for("codex", "gpt-6.1-sol") == 258_400
    before = cache.stat()

    sibling = home / "models_cache.tmp"
    sibling.write_text(json.dumps({"models": [{**_SOL, "context_window": 100000}]}), encoding="utf-8")
    os.utime(sibling, ns=(before.st_atime_ns, before.st_mtime_ns))
    os.replace(sibling, cache)
    after = cache.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert after.st_ino != before.st_ino

    assert context_window_for("codex", "gpt-6.1-sol") == 95_000
    assert len(parses) == 2


def test_pathologically_nested_content_is_a_cached_content_failure(tmp_path, monkeypatch) -> None:
    """`RecursionError` is not a `ValueError`, but it is as stable as malformed JSON for a file version."""
    home = _codex_home(tmp_path, monkeypatch)
    (home / "models_cache.json").write_text("[" * 200_000, encoding="utf-8")
    parses = _count_parses(monkeypatch)

    assert [context_window_for("codex", "gpt-6.1-sol") for _ in range(3)] == [None] * 3
    assert len(parses) == 1


def test_the_codex_config_model_is_read_once_per_file_version(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    reads = _count_calls(monkeypatch, "_parse_codex_model")

    assert [context_window_for("codex", None) for _ in range(4)] == [258_400] * 4
    assert len(reads) == 1


# --- windows a call reported ---------------------------------------------------


def test_an_observed_window_is_remembered_per_backend_and_model() -> None:
    observe_context_window("claude", "claude-sonnet-5-5", 1_000_000)

    assert context_window_for("claude", "claude-sonnet-5-5") == 1_000_000
    assert context_window_for("claude", "claude-opus-5-5") is None
    assert context_window_for("codex", "claude-sonnet-5-5") is None


def test_a_window_observed_without_a_model_serves_runs_that_select_none() -> None:
    """`claude -p` with no `--model` has `resolved_model` None; the report names the model it used."""
    observe_context_window("claude", None, 1_000_000)

    assert context_window_for("claude", None) == 1_000_000
    assert context_window_for("claude", "claude-sonnet-5-5") is None


@pytest.mark.parametrize("window", [0, -1, True, "1000000", None, 1.5])
def test_a_reported_window_that_is_not_a_positive_int_is_ignored(window: object) -> None:
    observe_context_window("claude", None, window)

    assert context_window_for("claude", None) is None


def test_an_observed_window_outranks_the_codex_catalog(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    observe_context_window("codex", "gpt-6.1-sol", 500_000)

    assert context_window_for("codex", "gpt-6.1-sol") == 500_000


def test_active_window_follows_the_scoped_backend_and_its_resolved_model(tmp_path, monkeypatch) -> None:
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    selected = CODEX_BACKEND.__class__(**{**CODEX_BACKEND.__dict__, "resolved_model": "gpt-6.1-sol"})

    with scoped_active_backend(selected):
        assert active_context_window() == 258_400
    with scoped_active_backend(CLAUDE_BACKEND):
        assert active_context_window() is None


# --- the Claude result envelope ------------------------------------------------


# --- the advisory uses it ------------------------------------------------------


def test_a_605kb_prompt_is_measured_against_each_lanes_own_resolved_window(tmp_path, monkeypatch) -> None:
    """The 384 KiB roadmap ceiling renders about 605 KB: `high` against the 200K default, `ok` once Claude's
    1M window is learned, and `warn` against Codex's 258K usable window."""
    total = 605_000
    _codex_home(tmp_path, monkeypatch, models=[_SOL])
    codex = dataclasses.replace(CODEX_BACKEND, resolved_model="gpt-6.1-sol")

    default = prompt_budget.estimate_prompt_budget(total, context_window=active_context_window())
    observe_context_window("claude", None, 1_000_000)
    claude = prompt_budget.estimate_prompt_budget(total, context_window=active_context_window())
    with scoped_active_backend(codex):
        codex_verdict = prompt_budget.estimate_prompt_budget(total, context_window=active_context_window())

    assert (default.level, default.window_defaulted) == (prompt_budget.LEVEL_HIGH, True)
    assert (claude.level, claude.window_defaulted) == (prompt_budget.LEVEL_OK, False)
    assert (codex_verdict.level, codex_verdict.window_defaulted) == (prompt_budget.LEVEL_WARN, False)


# --- every call site resolves the window ---------------------------------------


_EXPECTED_SITES = {"shell.py": 1, "review.py": 3, "create.py": 1, "detail.py": 3, "launcher.py": 3}


def test_every_budget_call_site_resolves_the_window_and_only_the_refusal_gate_excludes_observed() -> None:
    """The class this feature closes: every `estimate_prompt_budget` / `maybe_warn_prompt_budget` call
    outside the leaf passes `context_window=active_context_window()`. A new site that omits it, passes
    `None` or a literal, silently measures against the 200K default, which is the bug. The one site that
    may differ is the refusal gate, which passes `observed=False`. Per-module counts are exact, so a
    deleted site fails too."""
    root = Path(prompt_budget.__file__).parent
    offenders: list[str] = []
    counts: dict[str, int] = {}
    observed_false: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "prompt_budget.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name not in {"estimate_prompt_budget", "maybe_warn_prompt_budget"}:
                continue
            counts[path.name] = counts.get(path.name, 0) + 1
            keyword = next((k for k in node.keywords if k.arg == "context_window"), None)
            value = keyword.value if keyword is not None else None
            resolves = (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "active_context_window"
            )
            if not resolves:
                offenders.append(f"{path.name}:{node.lineno}")
            elif value.args or any(k.arg != "observed" for k in value.keywords):
                offenders.append(f"{path.name}:{node.lineno} (unexpected arguments)")
            elif value.keywords:
                observed_false.append(path.name)
    assert offenders == []
    assert counts == _EXPECTED_SITES
    assert observed_false == ["launcher.py"]


def test_the_leaf_imports_only_the_backend_leaf() -> None:
    """The module docstring claims it adds no edge to `shell` or `launcher`; pin it."""
    first_party: set[str] = set()
    for node in ast.walk(ast.parse(Path(context_window.__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("plan_tool"):
            first_party.add(node.module)
        elif isinstance(node, ast.Import):
            first_party.update(a.name for a in node.names if a.name.startswith("plan_tool"))
    assert first_party == {"plan_tool.backend"}
