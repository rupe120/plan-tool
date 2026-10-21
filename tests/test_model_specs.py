"""Unit tests for :mod:`plan_tool.model_specs`.

Hermetic by construction: every catalog comes through the injected
``fetcher=`` seam (a fixture string) or a ``tmp_path`` cache file — nothing
here touches the network. Mirrors the seam discipline the module docstring
calls out, so a regression that bypasses the seam shows up as a real HTTP
attempt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plan_tool import model_specs as ms
from plan_tool.model_specs import Catalog, ModelSpec


# A two-provider catalog shaped like models.dev ``api.json``.
FIXTURE = json.dumps(
    {
        "anthropic": {
            "name": "Anthropic",
            "models": {
                "claude-opus-4-8": {
                    "name": "Claude Opus 4.8",
                    "cost": {"input": 5, "output": 25},
                    "limit": {"context": 1_000_000, "output": 64_000},
                    "knowledge": "2025-01",
                },
                "claude-haiku-4-5": {
                    "name": "Claude Haiku 4.5",
                    "cost": {"input": 1, "output": 5},
                    "limit": {"context": 200_000, "output": 32_000},
                },
            },
        },
        "openai": {
            "name": "OpenAI",
            "models": {
                "gpt-5-codex": {
                    "name": "GPT-5 Codex",
                    "cost": {"input": 2, "output": 8},
                    "limit": {"context": 400_000, "output": 64_000},
                },
            },
        },
    }
)


def _catalog() -> Catalog:
    return ms.fetch_catalog(fetcher=lambda _url: FIXTURE)


def _spec(catalog: Catalog, model_id: str) -> ModelSpec:
    return next(s for s in catalog.specs if s.id == model_id)


class TestFetchAndParse:
    def test_fetch_via_seam_parses_every_model(self) -> None:
        cat = _catalog()
        assert cat.ok
        assert {s.id for s in cat.specs} == {
            "claude-opus-4-8", "claude-haiku-4-5", "gpt-5-codex"
        }

    def test_spec_fields_mapped(self) -> None:
        assert _spec(_catalog(), "claude-opus-4-8") == ModelSpec(
            id="claude-opus-4-8", provider="anthropic", name="Claude Opus 4.8",
            context_window=1_000_000, max_output=64_000,
            input_cost=5.0, output_cost=25.0, knowledge_cutoff="2025-01",
        )

    def test_malformed_entries_skipped_not_fatal(self) -> None:
        raw = json.dumps({
            "anthropic": {"models": {
                "good": {"limit": {"context": 10}},
                "bad-list": [],          # non-dict model → skipped
            }},
            "broken-provider": "nope",   # non-dict provider → skipped
        })
        cat = ms.fetch_catalog(fetcher=lambda _u: raw)
        assert [s.id for s in cat.specs] == ["good"]

    def test_fetch_failure_is_non_fatal(self) -> None:
        def boom(_url):
            raise OSError("no net")

        cat = ms.fetch_catalog(fetcher=boom)
        assert not cat.ok
        assert cat.error and "no net" in cat.error

    def test_parse_failure_is_non_fatal(self) -> None:
        cat = ms.fetch_catalog(fetcher=lambda _u: "{not json")
        assert not cat.ok and cat.error.startswith("parse failed")


class TestProviderAndDefault:
    def test_provider_alias(self) -> None:
        assert ms.provider_for_backend("codex") == "openai"
        assert ms.provider_for_backend("CLAUDE") == "anthropic"

    def test_provider_passthrough_for_unmapped(self) -> None:
        assert ms.provider_for_backend("mistral") == "mistral"

    @pytest.mark.parametrize(
        ("model", "backend"),
        [
            ("gpt-5.6-terra", "codex"),
            ("chatgpt-4o-latest", "codex"),
            ("o3-pro", "codex"),
            ("openai/gpt-5-codex", "codex"),
            ("claude-sonnet-4-5", "claude"),
            ("anthropic:claude-opus-4-6", "claude"),
            ("gemini-3-pro", "gemini"),
            ("google/gemini-3-pro", "gemini"),
            ("claude:anthropic/foo", "claude"),
            ("gpt-5.6:anthropic/foo", "codex"),
            ("anthropic.claude-3-5-sonnet-20241022-v2:0", "claude"),
            ("us.anthropic.claude-3-5-sonnet-20241022-v2:0", "claude"),
        ],
    )
    def test_backend_for_unambiguous_model_family(
        self, model: str, backend: str
    ) -> None:
        assert ms.backend_for_model(model) == backend

    @pytest.mark.parametrize("model", ("opus", "mistral-large", ""))
    def test_backend_for_ambiguous_model_is_none(self, model: str) -> None:
        assert ms.backend_for_model(model) is None

    def test_model_backend_aliases_derive_from_canonical_backend_aliases(self) -> None:
        assert ms._MODEL_BACKEND_ALIASES == {
            ms.provider_for_backend(backend): backend
            for backend in ms._MODEL_FAMILY_PREFIXES
        }

    def test_model_family_backend_names_derive_from_prefixes(self) -> None:
        assert ms.model_family_backend_names() == frozenset(ms._MODEL_FAMILY_PREFIXES)

    def test_model_family_backends_have_provider_aliases(self) -> None:
        assert set(ms._MODEL_FAMILY_PREFIXES) <= set(ms._BACKEND_PROVIDER_ALIASES)

    def test_synthesize_model_family_backend_rejects_unrecognized_name(self) -> None:
        assert ms.synthesize_model_family_backend("gemini").name == "gemini"
        with pytest.raises(ValueError, match="unknown model-family backend"):
            ms.synthesize_model_family_backend("typo")

    def test_synthesize_model_family_backend_resolves_registered_family_by_case(
        self,
    ) -> None:
        from plan_tool.backend import resolve_backend

        real_claude = resolve_backend("claude")
        resolved = ms.synthesize_model_family_backend("Claude")
        assert resolved is real_claude
        assert resolved.batch_argv("hi") == real_claude.batch_argv("hi")
        assert resolved.batch_argv("hi") != ["claude", "hi"]

    def test_model_family_docs_cover_every_supported_prefix(self) -> None:
        root = Path(__file__).parent.parent
        tokens = tuple(
            family if family[1:].isdigit() else f"{family}-*"
            for families in ms._MODEL_FAMILY_PREFIXES.values()
            for family in families
        )
        paths = (
            Path("plan_tool/cli/parser.py"),
            Path("docs/BACKENDS.md"),
            Path("RUNBOOK.md"),
            Path("docs/ARCHITECTURE.md"),
            Path("integrations/claude/SKILL.md"),
            Path("integrations/codex/SKILL.md"),
            Path("integrations/cursor/SKILL.md"),
        )
        for path in paths:
            text = (root / path).read_text(encoding="utf-8")
            missing = [token for token in tokens if token not in text]
            assert not missing, f"{path} is missing model-family docs for {missing}"

    def test_pick_flagship_by_context_then_cost(self) -> None:
        # Opus (1M ctx, $25 out) outranks Haiku (200K, $5).
        assert ms.pick_default_model(_catalog(), "anthropic").id == "claude-opus-4-8"

    def test_pick_none_for_unknown_provider(self) -> None:
        assert ms.pick_default_model(_catalog(), "google") is None

    def test_pick_none_for_failed_catalog(self) -> None:
        assert ms.pick_default_model(Catalog(error="x"), "anthropic") is None


class TestCache:
    def test_fresh_cache_short_circuits_fetch(self, tmp_path) -> None:
        cache = tmp_path / "api.json"
        calls = {"n": 0}

        def counting_fetcher(_url):
            calls["n"] += 1
            return FIXTURE

        first = ms.fetch_catalog(
            fetcher=counting_fetcher, cache_path=cache, now=1000.0
        )
        assert first.ok and not first.from_cache and calls["n"] == 1
        # Pin mtime to the injected clock so age math is deterministic
        # (real st_mtime is wall-clock; the injected ``now`` is not).
        os.utime(cache, (1000.0, 1000.0))

        # Within TTL: reads disk, fetcher untouched.
        second = ms.fetch_catalog(
            fetcher=counting_fetcher, cache_path=cache,
            now=1000.0 + 60, max_age_s=3600,
        )
        assert second.ok and second.from_cache and calls["n"] == 1

    def test_stale_cache_refetches(self, tmp_path) -> None:
        cache = tmp_path / "api.json"
        ms.fetch_catalog(fetcher=lambda _u: FIXTURE, cache_path=cache, now=1000.0)
        os.utime(cache, (1000.0, 1000.0))
        calls = {"n": 0}

        def counting_fetcher(_url):
            calls["n"] += 1
            return FIXTURE

        # Past TTL → fetch again.
        result = ms.fetch_catalog(
            fetcher=counting_fetcher, cache_path=cache,
            now=1000.0 + 10_000, max_age_s=3600,
        )
        assert result.ok and not result.from_cache and calls["n"] == 1
