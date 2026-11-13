# Step 2 — Add a command model default to existing selection

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Accept a validated command model as an optional input to the existing effective-backend selector. Keep all model precedence in that owner and preserve fallback behavior.

## Table of Contents

- [Why](#why) — Purpose.
- [Files](#files) — Edit footprint.
- [Implementation](#implementation) — Smallest delivery path.
- [Tests](#tests) — Evidence.
- [Acceptance criteria](#acceptance-criteria) — Completion checks.

## Why

The selector needs one extra model default between the explicit model and the backend-wide model. It does not need command names or a CLI registry.

## Files

Edit `plan_tool/backend.py`, `tests/test_backend.py`, `tests/test_shell.py`, and `tests/test_launcher.py`. Production recovery loops remain unchanged; create no files.

## Implementation

Extend `_select_effective_backend` and `select_active_backend` with an optional keyword-only `command_model=None`. The CLI supplies this string from step 1's validated configuration for the selected backend and canonical command. The selector never parses command keys or imports CLI code.

Resolve in one place: explicit `model`, then `command_model`, then the selected backend's existing project `model`, then manifest `default_model`, then omission. Keep `build_effective_backend` unchanged, including extras, prompt transport, model-flag checks, descriptor identity on the no-op path, and registry immutability. Retain synthesis and unknown-override diagnostics.

Commandless callers omit the new input and retain their existing behavior. In particular, `scoped_select_active_backend` and the callers at `shell.py:_select_rate_limit_backend` and `launcher.py:_select_rate_limit_backend` remain unchanged: fallback gets its own backend-wide model and restores the primary effective descriptor. Do not propagate the primary command model or explicit model into fallback selection.

## Tests

Use unmarked tests and fake subprocesses. Parameterize the five model sources, absent/defaulted new input, and batch/streaming argv. Assert the selected descriptor's `resolved_model`, registry preservation, and no-op identity.

Extend the existing shell and launcher switch-success/failure tests through real scoped selection. Configure different primary, fallback-base, and fallback-command models; assert fallback uses its base model and restores the exact primary descriptor after success or failure. Reuse existing test seams rather than adding another recovery harness.

Run `uv run pytest tests/test_backend.py tests/test_shell.py tests/test_launcher.py -q`, then the full suite before accepting the code step. Temporarily swap model precedence to verify the corresponding matrix case fails.

## Acceptance criteria

- Model selection follows the five-source order through one existing owner.
- Both argv paths receive the same model without mutating registry descriptors.
- Existing callers and fallback selection retain their behavior when the new input is omitted.
- Focused and full tests pass without real backend calls.
