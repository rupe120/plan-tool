"""Implementation benchmark corpus — two spec'd steps + their HIDDEN tests.

This module is the answer key for the *implementation* family. The backend is
given ONLY the two step specs and the embedded scratch-repo seed below; it
never sees the ``test_*`` functions in this file. After the backend implements
the steps into a copy of the seed, the step-2 engine drops this file into the
scratch repo and runs it with the plan's ``test_command``
(``uv run pytest <this file> -q --tb=no``). Scoring is judge-free: the pytest
exit code is the hidden-test pass signal, and out-of-scope edits are counted by
``plan_tool/scope_guard.py:evaluate_apply_scope`` (paths outside
``compute_in_scope_paths``, excluding ``is_documentation`` files).

The tests import the implementation lazily INSIDE each test body, so this file
*collects* under pytest even before ``solution.py`` exists — collection
succeeds, the tests fail until the seed is implemented. That collect-without-
implementation property is what the step-1 verification checks.

================================================================================
STEP SPEC 1 — slugify
================================================================================
Implement ``slugify(text: str) -> str`` in ``solution.py``:
  - lowercase the text;
  - replace each run of whitespace with a single hyphen;
  - drop every character that is not an ASCII letter, digit, or hyphen;
  - collapse repeated hyphens and strip leading/trailing hyphens.
Examples: ``slugify("Hello, World!") == "hello-world"``;
``slugify("  A  B  ") == "a-b"``; ``slugify("--x--") == "x"``.
In-scope footprint: ``solution.py`` only.

================================================================================
STEP SPEC 2 — truncate_words
================================================================================
Implement ``truncate_words(text: str, max_words: int) -> str`` in
``solution.py``:
  - split on whitespace;
  - if the text has ``max_words`` or fewer words, return it unchanged
    (original spacing need not be preserved — single spaces are fine);
  - otherwise return the first ``max_words`` words joined by single spaces,
    followed by a single trailing ``"..."`` (three ASCII dots, no space before).
Examples: ``truncate_words("a b c", 5) == "a b c"``;
``truncate_words("a b c d", 2) == "a b..."``.
In-scope footprint: ``solution.py`` only.

================================================================================
EMBEDDED SCRATCH-REPO SEED  (path -> contents; materialized by the engine)
================================================================================
solution.py:

    # Implement slugify and truncate_words per the bench step specs.
    # (A comment, not a docstring: this seed is embedded inside the
    # corpus module's own docstring, where literal triple-quotes can't
    # appear and escaped ones would materialize as a syntax error.)


    def slugify(text):
        raise NotImplementedError


    def truncate_words(text, max_words):
        raise NotImplementedError

================================================================================
"""

# --- HIDDEN TESTS (withheld from the backend) ----------------------------------
# Imports are intentionally deferred into each test body so this module collects
# under pytest before solution.py is implemented.


def test_slugify_basic_punctuation():
    from solution import slugify

    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_and_strips():
    from solution import slugify

    assert slugify("  A  B  ") == "a-b"
    assert slugify("--x--") == "x"


def test_truncate_words_under_limit_is_unchanged():
    from solution import truncate_words

    assert truncate_words("a b c", 5) == "a b c"


def test_truncate_words_over_limit_appends_ellipsis():
    from solution import truncate_words

    assert truncate_words("a b c d", 2) == "a b..."
