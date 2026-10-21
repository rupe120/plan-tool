> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Redact tool-input summaries in the codex and cursor native producers, and bring RUN_FLOW.md current

## Summary

Extends step 7's redact-then-truncate scrub from `plan_tool/backend.py:_summarize_tool_input` to the two producers that never call it — `_codex_tool_use_summary` and `_cursor_tool_use_summary` — by running the same scrub pass on each branch's own untruncated candidate string before its existing `[:_TOOL_INPUT_SUMMARY_CAP]` slice, then removing the literal `"[OMITTED]"` suppression step 7 placed at their two call sites in `_codex_parse_stream_line` and `_cursor_parse_stream_line`. The key design decision: the scrub runs inside the producer functions on pre-truncation text, never over the already-returned, already-truncated string at the call sites — that ordering is what stops a secret straddling the 200-character cap from leaking its leading bytes. As the plan's last step, it also rewrites `docs/RUN_FLOW.md`'s "Rate-limit / transient recovery seam" section and source map, which still say batch calls spawn via `subprocess.run` and describe a bare wait/sleep window — none of the shared runner, the seven-value termination-reason vocabulary, the observer contract, or the recovery-wait/interrupt events steps 2–9 built. Green when all three backends' tool-use summaries redact the same secret inputs identically, `[OMITTED]` is gone from `plan_tool/backend.py`, and the flow doc describes what actually ships.

## Table of Contents

- [Summary](#summary) — what gets redacted, where the scrub runs, and the doc sweep
- [Why](#why) — the suppression debt step 7 left and the stale doc it named this step to fix
- [Input](#input) — the step 7 scrub contract and the steps 2–9 facts the doc rewrite describes
- [Files (creates vs edits)](#files-creates-vs-edits) — the three declared files, no new ones
- [Implementation](#implementation) — the per-branch scrub, the unsuppression, and the doc rewrite
- [Tests](#tests) — the redaction roster plus the step-7 suppression tests this step rewrites
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — background for the stream shapes and the doc's subject matter
- [Applicable guardrails](#applicable-guardrails) — plan fences this step's edits sit inside
- [Deferred](#deferred) — what stays out, and where it goes instead

## Why

Step 7 shipped real redaction only for `_summarize_tool_input`'s two call sites — `_claude_parse_stream_line`'s `tool_use` branch and `_cursor_parse_assistant_blocks`'s `tool_use` branch (the claude-shaped blocks cursor also emits). The two producers with their own native tool-call event shapes — `_codex_tool_use_summary` (codex `command_execution`/`file_change` items) and `_cursor_tool_use_summary` (cursor's own `tool_call` event, distinct from the blocks it shares with claude) — hand back pre-formatted strings and were deliberately suppressed to the literal `"[OMITTED]"` instead, with real redaction named as this step's work. That suppression is safe but useless: an operator watching a `-v` codex or cursor batch call sees `[OMITTED]` for every tool use, which defeats the visibility this plan exists to provide. Separately, `docs/RUN_FLOW.md`'s "Rate-limit / transient recovery seam" section still opens with "`shell.claude_invoke` (batch `subprocess.run`) and `launcher.shell_invoker` (streaming `Popen`)" and its seam table's `run_once` row says "batch `subprocess.run` vs streaming `Popen`" — false since step 6 moved both lanes onto `plan_tool/backend_runner.py:run_streaming_once` — and nothing in the doc mentions the termination-reason vocabulary (step 4), the `backend_recovery_wait`/`run_interrupted` events on the wait/sleep seams (step 5), or the observer contract (step 7). Leaving a flow doc describing a deleted architecture is exactly the stale-history failure this repo works hardest to avoid.

## Input

- **Step 7's scrub helper and pattern constants in `plan_tool/backend.py`** — the redact pass this step reuses: the known secret-prefix token list (`Authorization:`/`Bearer `-shaped values plus bare `sk-`/`ghp_`/`gho_`/`AKIA`/`xox` prefixes), the 20+-character mixed-character-class run heuristic, and the `[REDACTED]` replacement token. Step 7's detail proposes these; read the landed helper name, signature, and pattern set off the module at HEAD — the landed names win over any name the plan or step 7's prose suggested. This step calls that helper; it must not copy or re-derive the patterns.
- **Step 7's two suppression sites** — `_codex_parse_stream_line`'s `item.started` branch and `_cursor_parse_stream_line`'s `tool_call`/`subtype == "started"` branch replace each producer's summary with `"[OMITTED]"` before it lands in the `tool_use` event's `tool_input_summary` field, and step 7's tests pin that. Those tests going red here is the expected outcome of finishing the class, not a regression.
- **Steps 2–9's landed run-lane facts** — the doc rewrite describes the shared runner (`plan_tool/backend_runner.py:run_streaming_once`, steps 2–4), the seven-value termination-reason vocabulary (step 4), the `backend_spawn`/`backend_termination`/`backend_recovery_wait`/`run_interrupted` events and the wrapped wait/sleep seams (step 5), the batch lane's move onto the runner (step 6), the observer contract (step 7), and interrupt handling (step 8). Cite each by reading the landed code, not the sibling detail files — details are proposals; the code is what shipped.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/backend.py` — run the step-7 scrub on each untruncated candidate inside `_codex_tool_use_summary` (both branches) and `_cursor_tool_use_summary` (all three value-returning sites); delete the `"[OMITTED]"` substitution at the two parse-branch call sites.
- `tests/test_backend.py` — rewrite step 7's suppression-pinning tests for these two producers into redaction assertions; add the new redaction cases listed under Tests; restore real-summary assertions in the fixture-driven codex/cursor tool-use tests if step 7 weakened them to expect `[OMITTED]`.
- `docs/RUN_FLOW.md` — rewrite the "Rate-limit / transient recovery seam" section's stale spawn-mechanics claims, add the shared-runner / termination-vocabulary / observer / recovery-event facts, and extend the source map for every newly cited symbol.

## Implementation

### Redaction: scrub each branch's candidate before its existing slice

- **`_codex_tool_use_summary`** has two return sites, each already ending in `[:_TOOL_INPUT_SUMMARY_CAP]`:
  - the `command_execution` branch's candidate is the command string — scrub it, then slice;
  - the `file_change` branch's candidate is the joined `", ".join(parts)` string — scrub the joined whole once, then slice. Do not scrub per path part: the step's fence is one pass over the branch's whole candidate, so the producer never needs an enumerated field list to stay covered.
- **`_cursor_tool_use_summary`** returns from three sites inside its `*ToolCall`-key loop (the `command`, `path`, and `target` values), each already sliced to the cap — scrub each candidate before its slice. The final `("tool", "")` return carries no text and needs nothing.
- **Reuse step 7's helper, don't reinvent.** The scrub is a call to the pattern helper step 7 landed beside `_summarize_tool_input` in the same module — same prefix list, same character-class heuristic, same `[REDACTED]` token. If the landed helper's shape doesn't fit a producer's string directly, adapt the call, never the patterns: a second pattern list is the drift this step's fence exists to prevent.
- **The rejected alternative — scrubbing at the call sites** (wrapping each producer's returned string inside `_codex_parse_stream_line` / `_cursor_parse_stream_line`) is wrong twice over: the returned string is already truncated, so a secret straddling the cap has already leaked its leading bytes; and it leaves the producers unsafe for any future caller. The scrub belongs inside the producers, on pre-truncation text.

### Unsuppress the two call sites

- Delete the `"[OMITTED]"` substitution step 7 placed where `_codex_tool_use_summary`'s result feeds the `tool_use` event in `_codex_parse_stream_line`'s `item.started` branch, and where `_cursor_tool_use_summary`'s result feeds the same field in `_cursor_parse_stream_line`'s `tool_call`/`started` branch. The producers' own output is now safe.
- **Do not touch** `_cursor_parse_assistant_blocks`'s `tool_use` branch (already redacted for real via `_summarize_tool_input` since step 7 — adding a second scrub there would double-process) or `plan_tool/backend_runner.py`'s `redaction_ready=False` fail-closed branch (a separate mechanism for callers that opt out; it stays).

### `docs/RUN_FLOW.md`: rewrite the recovery-seam section and source map

- **Fix the spawn-mechanics claims.** The section's opening ("batch `subprocess.run`" / "streaming `Popen`") and the seam table's `run_once(attempt)` difference column describe an architecture step 6 deleted — both lanes now spawn through `plan_tool/backend_runner.py:run_streaming_once`. Rewrite in present tense; delete the old claims rather than annotating them. Claims that remain true survive unchanged — the `retry_guard` row's launcher-vs-shell difference (git-delta guard vs `ALWAYS_RETRY`) is still real, as is the whole inject-don't-unify stance.
- **Add what steps 2–9 built**, at the terse level this doc already uses: the shared runner and its heartbeat/stall/silence-kill supervision; the closed termination-reason vocabulary (name the landed constant or enum, don't enumerate the seven values if the code owns the list); the observer contract batch callers pass (step 7) versus the bare writer `run` passes; the `backend_recovery_wait`/`run_interrupted` events the wrapped wait/sleep seams emit (step 5), which close the previously silent between-attempt window; and one line on tool-input-summary redaction (steps 7 and this one) so the doc explains why `-v` summaries can show `[REDACTED]`.
- **Extend the source map** with a row for every newly cited symbol — at minimum `plan_tool/backend_runner.py` (`run_streaming_once`) and the redaction surface in `plan_tool/backend.py`. This doc family's contract is that the source map covers every cited symbol; a new citation without a map row breaks it.
- **Read names off HEAD.** Every symbol, event name, and vocabulary member the rewrite cites must be verified against the landed code at write time — the sibling details' proposed names lose to what shipped.

## Tests

All cases live in `tests/test_backend.py`, alongside the existing `test_codex_*` / `test_cursor_*` roster and its `_parse_codex_fixture` / `_parse_cursor_fixture` helpers.

### Tests for this step

- `test_codex_command_summary_redacts_known_prefix_token` — a `command_execution` item whose command embeds a `Bearer `/`sk-`-shaped token; the emitted `tool_input_summary` contains `[REDACTED]` and none of the token's bytes, while the command's benign text survives.
- `test_codex_file_change_summary_redacts_secret_segment` — a `file_change` item with a 20+-character mixed-class run in one path; the joined summary redacts it.
- `test_codex_summary_redacts_before_truncating` — a secret positioned to straddle the `_TOOL_INPUT_SUMMARY_CAP` cutoff is fully redacted, proving scrub-then-slice ordering.
- `test_cursor_native_tool_call_summary_redacts_all_three_branches` — parametrized over the `command`, `path`, and `target` return sites, each with an embedded secret; each emitted summary is redacted.
- `test_cursor_summary_redacts_before_truncating` — the straddle case through cursor's native producer.
- `test_all_three_backends_redact_the_same_input_identically` — one parametrized case feeding the same secret-bearing string through claude's `_summarize_tool_input` Bash branch, codex's command branch, and cursor's command branch; all three produce the same redacted result. This is the shared-pass guard: a future pattern edit that reaches only one producer fails here loudly.
- `test_benign_summaries_pass_through_unredacted` — the existing fixture strings (`hello-from-codex`, `tool_probe_ok`, `note.txt`) survive unchanged, guarding against over-redaction of ordinary commands and paths.
- **Rewrites of step 7's suppression tests** — the cases step 7 added pinning `"[OMITTED]"` on these two producers (its detail names `test_codex_tool_use_summary_result_is_omitted_in_the_event`; read the landed roster for the cursor counterpart and any fixture-driven test weakened to expect `[OMITTED]`) flip to asserting real redacted summaries. Expect them red when the unsuppression lands — that is the class sweep completing, not a reason to narrow it.

Green-before-done gate: every case above, plus the untouched remainder of `tests/test_backend.py` and the full suite, must be green before this step is finished.

Doc verification (no unit tests own a markdown file): `rg 'subprocess\.run' docs/RUN_FLOW.md` returns nothing; `rg 'backend_runner' docs/RUN_FLOW.md` hits both the seam section and the source map; every symbol the rewritten section cites appears in the source map; the section carries no past-tense narration of the pre-runner architecture.

## Acceptance criteria

- `_codex_tool_use_summary` and `_cursor_tool_use_summary` redact a known-prefix token and a 20+-character mixed-class run to `[REDACTED]` on every value-returning branch, before truncation — the straddle tests pass for both.
- The same secret input produces the same redacted output through all three backends' producers (the parametrized shared-pass test passes).
- `rg 'OMITTED' plan_tool/backend.py` returns nothing; `plan_tool/backend_runner.py`'s `redaction_ready` fail-closed branch is unchanged (zero diff to that file).
- The fixture-driven codex/cursor tool-use tests assert real, unredacted summaries for the fixtures' benign text.
- `plan_tool/backend.py` contains exactly one set of redaction pattern definitions — the step-7 helper — and both native producers call it (no second pattern list; checkable by grepping the prefix tokens, which appear once).
- `docs/RUN_FLOW.md`'s recovery-seam section names the shared runner, the termination-reason vocabulary, the observer contract, and the `backend_recovery_wait`/`run_interrupted` events; no sentence claims batch calls spawn via `subprocess.run`; the source map has a row for every newly cited symbol.
- Full suite green: `uv run pytest tests/ -q -n auto`.

## References

- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — the stream-json message objects whose `tool_use` blocks carry the inputs being summarized and redacted.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — the `--verbose` output whose tool-use lines change content (redacted summaries) without any invocation-shape change.
- [JSON Lines specification](https://jsonlines.org/) — the NDJSON framing all three parsers consume; redaction operates on parsed field values, never on raw lines.

## Applicable guardrails

- **The plan's "## Step intent" fence** — scope is exactly the two native producers plus the RUN_FLOW.md sweep. The scrub reuses step 7's landed pattern definitions, runs on each branch's untruncated candidate before its existing slice, and never scans the returned string or enumerates fields per producer. Claude's and cursor's shared `_summarize_tool_input` path is already covered by step 7 and gets zero diff here.
- **The plan's "## Out of scope", raw provider transcripts** — redaction applies only to the `tool_input_summary` event field. No raw-NDJSON-line capture, scan, or scrub anywhere in this step.
- **The plan's "## Out of scope", `runs show` / `runs watch`** — the RUN_FLOW.md rewrite documents the JSONL/`in-flight.json` surfaces an operator reads directly; it must not describe or promise a CLI viewer.
- **The plan's "## Plan intent", unchanged parsing and contracts** — the producers change only the summary string's content; event shapes, `tool_name` values, stats extraction, and every parse branch stay as they are, which is what keeps the existing fixture round-trip tests meaningful.

## Deferred

- Raw-transcript capture and redaction of raw stream lines — the carved-out follow-on plan's concern per the plan's Out of scope; this step redacts one event field only.
- Making the redaction pattern list configurable per backend or per project — no step in this plan builds configuration surface; file a `BACKLOG.md` entry if a real need appears.
- Consolidating the three summary producers into one shared function — they parse three genuinely different event shapes; folding them is a cross-shape refactor this feature step cannot mint. The shared-pass test pins the property that matters (identical redaction) without the merge; route any consolidation proposal to `BACKLOG.md` with machine-verified evidence per that file's consolidation rules.
- Doc sweeps beyond `docs/RUN_FLOW.md` (README's runner mentions, `docs/ARCHITECTURE.md`) — earlier steps own the doc edits their own changes imply; this step's declared doc scope is the flow doc the plan names.
