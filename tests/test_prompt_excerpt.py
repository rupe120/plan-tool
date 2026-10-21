"""Tests for symbol-aware prompt excerpts."""

from __future__ import annotations

from plan_tool.prompt_excerpt import build_prompt_excerpt


def test_python_function_symbol_window_beats_file_header() -> None:
    text = "\n".join(f"# header {i}" for i in range(80))
    text += "\n\n\ndef target_symbol():\n    return 1\n"

    excerpt = build_prompt_excerpt(
        "pkg/mod.py", text, ["target_symbol"], max_bytes=200
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "def target_symbol()" in excerpt.text
    assert "# header 0" not in excerpt.text


def test_python_symbol_window_preserves_imports_when_budget_allows() -> None:
    text = (
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "# setup noise\n"
        "VALUE = 1\n"
        "\n"
        "def wanted():\n"
        "    return Path(os.getcwd())\n"
    )

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["wanted"], max_bytes=500)

    assert excerpt.excerpt_kind == "symbol"
    assert "import os" in excerpt.text
    assert "from pathlib import Path" in excerpt.text
    assert "def wanted()" in excerpt.text


def test_python_symbol_window_marks_omitted_imports_when_budget_excludes_it() -> None:
    imports = "\n".join(f"import module_{i}" for i in range(60))
    text = f"{imports}\n\n\ndef wanted():\n    return 1\n"

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["wanted"], max_bytes=120)

    assert excerpt.excerpt_kind == "symbol"
    assert "def wanted()" in excerpt.text
    assert "_(truncated)_" in excerpt.text
    assert "import module_0" not in excerpt.text


def test_python_symbol_window_marks_a_dropped_gap_between_imports_and_symbol() -> None:
    # A helper between the import block and the matched symbol is dropped
    # from the excerpt even when import_text + symbol_text together fit
    # the byte budget -- the rendered text must still show the truncation
    # marker in that gap, not read as though the two were contiguous.
    text = (
        "import os\n"
        "\n"
        "def unrelated_helper():\n"
        "    return 1\n"
        "\n"
        "def wanted():\n"
        "    return os.getcwd()\n"
    )

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["wanted"], max_bytes=500)

    assert excerpt.excerpt_kind == "symbol"
    assert excerpt.truncated is True
    assert "import os" in excerpt.text
    assert "def wanted()" in excerpt.text
    assert "_(truncated)_" in excerpt.text
    assert "unrelated_helper" not in excerpt.text


def test_python_class_symbol_window_includes_decorator_context() -> None:
    text = "def setup():\n    pass\n\n@decorator\nclass Service:\n    pass\n"

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["Service"], max_bytes=200)

    assert excerpt.excerpt_kind == "symbol"
    assert "@decorator" in excerpt.text
    assert "class Service" in excerpt.text


def test_python_assignment_symbol_window() -> None:
    text = "# module\n\nTARGET_VALUE = 42\n\ndef unrelated():\n    pass\n"

    excerpt = build_prompt_excerpt(
        "pkg/mod.py", text, ["TARGET_VALUE"], max_bytes=200
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "TARGET_VALUE = 42" in excerpt.text
    assert "def unrelated" not in excerpt.text


def test_python_local_assignment_does_not_beat_later_function_match() -> None:
    text = (
        "def setup():\n"
        "    target_symbol = 1\n"
        "    return target_symbol\n"
        "\n\n"
        "def target_symbol():\n"
        "    return 2\n"
    )

    excerpt = build_prompt_excerpt(
        "pkg/mod.py", text, ["target_symbol"], max_bytes=200
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "def target_symbol()" in excerpt.text
    assert "target_symbol = 1" not in excerpt.text


def test_multiple_symbols_prefers_first_real_match() -> None:
    text = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["beta", "alpha"], max_bytes=200)

    assert excerpt.excerpt_kind == "symbol"
    assert "def beta()" in excerpt.text
    assert "def alpha()" not in excerpt.text


def test_invalid_python_uses_bounded_fallback() -> None:
    text = "def broken(:\n" + ("x" * 500)

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["broken"], max_bytes=80)

    assert excerpt.excerpt_kind == "fallback"
    assert excerpt.fallback_reason == "parse-error"
    assert excerpt.truncated is True
    assert "fallback preview: parse-error" in excerpt.text
    assert len(excerpt.text.encode("utf-8")) <= 80


def test_fallback_metadata_uses_stable_vocabulary() -> None:
    parse_error = build_prompt_excerpt("bad.py", "def x(:\n", ["x"], max_bytes=100)
    no_match = build_prompt_excerpt(
        "ok.py", "def y():\n    pass\n", ["x"], max_bytes=100
    )
    unsupported = build_prompt_excerpt("notes.yaml", "x: 1\n", ["x"], max_bytes=100)

    assert parse_error.excerpt_kind == "fallback"
    assert parse_error.fallback_reason == "parse-error"
    assert "fallback preview" in parse_error.text
    assert no_match.excerpt_kind == "fallback"
    assert no_match.fallback_reason == "no-symbol-match"
    assert "fallback preview" in no_match.text
    assert unsupported.excerpt_kind == "fallback"
    assert unsupported.fallback_reason == "unsupported-file-type"
    assert "fallback preview" in unsupported.text


def test_markdown_heading_symbol_window_uses_matching_section() -> None:
    text = (
        "# Plan\n\n"
        "intro\n\n"
        "## First\n\n"
        "first body\n\n"
        "## Target Section\n\n"
        "target body\n\n"
        "## Later\n\n"
        "later body\n"
    )

    excerpt = build_prompt_excerpt(
        "details/step.md", text, ["Target"], max_bytes=200
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "## Target Section" in excerpt.text
    assert "target body" in excerpt.text
    assert "first body" not in excerpt.text
    assert "later body" not in excerpt.text


def test_markdown_heading_matching_prefers_candidate_order() -> None:
    text = (
        "# Plan\n\n"
        "## Secondary\n\n"
        "secondary body\n\n"
        "## Primary\n\n"
        "primary body\n"
    )

    excerpt = build_prompt_excerpt(
        "details/step.md", text, ["Primary", "Secondary"], max_bytes=200
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "## Primary" in excerpt.text
    assert "primary body" in excerpt.text
    assert "secondary body" not in excerpt.text


def test_non_python_regex_match_uses_symbol_line_window() -> None:
    text = "\n".join(
        [
            "const prelude = 1;",
            "const other = 2;",
            "export function targetSymbol() {",
            "  return other;",
            "}",
            "const after = 3;",
        ]
    )

    excerpt = build_prompt_excerpt("src/app.ts", text, ["targetSymbol"], max_bytes=200)

    assert excerpt.excerpt_kind == "symbol"
    assert "targetSymbol" in excerpt.text


def test_non_python_regex_matching_prefers_candidate_order() -> None:
    text = "\n".join(
        [
            "const secondary = 1;",
            "const filler = 2;",
            "const filler = 3;",
            "const filler = 4;",
            "const filler = 5;",
            "const primary = 6;",
        ]
    )

    excerpt = build_prompt_excerpt(
        "src/app.ts", text, ["primary", "secondary"], max_bytes=180
    )

    assert excerpt.excerpt_kind == "symbol"
    assert "primary" in excerpt.text
    assert "secondary" not in excerpt.text


def test_no_symbol_match_returns_leading_excerpt() -> None:
    text = "def actual():\n    pass\n"

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["missing"], max_bytes=200)

    assert excerpt.excerpt_kind == "fallback"
    assert excerpt.fallback_reason == "no-symbol-match"
    assert "fallback preview: no-symbol-match" in excerpt.text
    assert "def actual()" in excerpt.text


def test_excerpt_marks_truncation_when_content_omitted() -> None:
    text = "def missing():\n    pass\n" + ("x" * 500)

    excerpt = build_prompt_excerpt("pkg/mod.py", text, ["other"], max_bytes=100)

    assert excerpt.truncated is True
    assert "_(truncated)_" in excerpt.text
