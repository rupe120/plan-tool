# Step 6 — Gate the `plan-tool security` next-step pointer behind a cheap, no-Claude relevance scan + a `--no-security-hint` opt-out

## Summary

Layers two opt-out controls on top of step 5's unconditional `plan-tool security <name>` pointer. Adds a pure, no-Claude predicate `security_hint_is_relevant(plan)` plus a curated `SECURITY_HINT_KEYWORDS` frozenset to `plan_tool/security_audit.py` (the orchestrator step 1 creates): it lowercases and **exact-token** scans the plan title + every step title + every declared file path (`Step.all_files`) and returns `True` iff any token is a security keyword. Adds a global `--no-security-hint` flag to `plan_tool/cli/parser.py:make_base_parser` — the one in-scope parser file whose flags reach **both** emission sites (`detail` lives in `authoring.py`, `completeness-audit`'s subparser lives in the out-of-scope `completeness_cmd.py`). Wraps step 5's `_print_next_steps("Security check:", …)` call in `plan_tool/cli/authoring.py:cmd_detail` and **both** branches of `plan_tool/cli/completeness_phases.py:_persist_and_present_report` so the pointer prints only when `not args.no_security_hint and security_hint_is_relevant(plan)`. **Load-bearing decision:** the gate is exact-token (not substring) so `auth` never matches `authoring`/`author`, and it is low-stakes — a wrong verdict only shows or hides one stderr line, never gates an audit pass and never spends Claude. On green, a security-relevant plan still prints the pointer, a plain plan (or `--no-security-hint`) prints nothing, and the completeness `--json` payload + grouped report bytes are unchanged.

## Table of Contents

- [Why](#why) — why a gate + opt-out lands now, on top of step 5's always-on pointer
- [Files (creates vs edits)](#files-creates-vs-edits) — three production edits, two test files, plus the regenerated golden
- [Implementation](#implementation) — the predicate, the keyword set, the global flag, and the two wrapped emission sites
- [Tests](#tests) — predicate purity, the auth/author guard, emission/suppression at both sites
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse + OWASP/CWE grounding for the keyword set
- [Deferred](#deferred) — Claude-scored relevance, per-keyword weighting, resolver consolidation

## Why

- **Step 5 emits the `plan-tool security` pointer unconditionally** — at the tail of every clean `detail` and `completeness-audit` run, regardless of whether the plan has any security surface. A plan that adds pagination or renames a metric gets the same nudge as one that adds OAuth, which trains operators to ignore the line.
- **A cheap relevance gate makes the pointer signal, not noise** — a keyword scan of content the plan already carries (title, step titles, declared file paths) is enough to suppress the pointer on plans with no plausible security surface, at zero Claude cost.
- **The gate must stay low-stakes by construction** — it gates a one-line advisory suggestion, never an audit pass. A false negative hides a suggestion the operator can still run by hand; a false positive shows one extra line. Neither spends Claude, so a simple deterministic scan is the right tool, not a model call.
- **`--no-security-hint` is the explicit escape hatch** — for operators who never want the nudge (CI authoring loops, scripted pipelines), independent of the relevance verdict.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/security_audit.py` (created in step 1, extended in steps 2/4) — add the module-level `SECURITY_HINT_KEYWORDS: frozenset[str]` constant and the pure `security_hint_is_relevant(plan) -> bool` predicate. No new internal/third-party imports (uses stdlib `re` only; the `Plan`/`Step` types are duck-read, not imported).
- `plan_tool/cli/parser.py` — add one `--no-security-hint` argument to `make_base_parser` (`action="store_true"`, `dest="no_security_hint"`), sited in the global-flag block alongside `--no-wait-on-rate-limit` / `--prompt-mode`.
- `plan_tool/cli/authoring.py` — in `cmd_detail`, wrap step 5's `_print_next_steps("Security check:", …)` call (the one immediately after the review/run/jira `"Next steps:"` block, inside `if rc == 0 and wrote and not args.dry_run:`) in the relevance + opt-out gate. Add top-imports `from plan_tool.parser import parse_plan` and `from plan_tool.security_audit import security_hint_is_relevant`.
- `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`, compute `show_security_hint` once, then gate step 5's `_print_next_steps("Security check:", …)` call in **both** the `if iterate_enabled:` branch and the `else:` audit-only branch. Add a body-local `from plan_tool.security_audit import security_hint_is_relevant` next to the existing `from plan_tool.completeness_report import (...)` import.

**Test files (edits):**

- `tests/cli/test_completeness_cmd.py` — extend `TestPersistAndPresentReport` with the completeness emission/suppression/irrelevance cases, plus a parse-contract case for the global flag (drives `plan_tool.cli.app.build_parser`).
- `tests/cli/test_authoring_cmds.py` — add the `cmd_detail` emission/suppression/irrelevance cases (the live authoring test module; the step's `files:` does not name it but the detail-emission gate lives in `authoring.py`, so its cases belong here per the `plan_tool/cli/X.py → tests/cli/test_X_cmds.py` convention).
- `tests/test_security_audit.py` (created in step 1) — add the pure-predicate cases. Not in the declared `files:`, but the gate is a pure function on `security_audit.py`, so its direct unit tests belong in the mirror module per `plan_tool/X.py → tests/test_X.py`.

**Beyond declared `files:` (required, mechanical):**

- `tests/cli/package_surface_help.golden.txt` — **must be regenerated.** Adding a flag to `make_base_parser` adds `[--no-security-hint]` to the top-level `plan-tool --help` usage line that `tests/cli/test_package_surface.py:test_help_matches_golden` pins. Regenerate by deleting the golden and re-running that test (it self-seeds and skips on the seeding run), exactly as a new global flag would require. This is a snapshot artifact, not logic — `tests/cli/test_package_surface.py` itself is unchanged.

## Implementation

### `plan_tool/security_audit.py` — the relevance predicate (foundational logic)

- **Add `SECURITY_HINT_KEYWORDS: frozenset[str]`** — a curated set of full-word security tokens, each a complete token (never a bare prefix). Representative members (the exact set is curated, OWASP/CWE-grounded):
  - identity/access: `auth`, `authn`, `authz`, `authentication`, `authorization`, `login`, `logout`, `oauth`, `sso`, `saml`, `jwt`, `rbac`, `permission`, `permissions`, `privilege`, `privileges`
  - secrets/crypto: `password`, `passwd`, `secret`, `secrets`, `credential`, `credentials`, `apikey`, `encrypt`, `encryption`, `decrypt`, `crypto`, `tls`, `ssl`, `https`, `certificate`, `kms`, `vault`
  - injection/web: `injection`, `xss`, `csrf`, `ssrf`, `sanitize`, `cors`, `csp`, `deserialize`
  - vuln vocabulary: `vulnerability`, `cve`, `cwe`, `exploit`, `pii`, `gdpr`, `hipaa`
- **Add `security_hint_is_relevant(plan) -> bool`** — the pure, no-Claude, no-I/O predicate:
  - **Build the haystack** from `plan.title`, every `step.title`, and every path in `step.all_files` (the order-preserving, de-duplicated `files` + `creates` accessor on `plan_tool/schema.py:Step`, already consumed across `plan_tool/` — `scope_guard.py`, `launcher.py`, `jira.py`, `review.py`, `detail.py`, `gates.py`, `create.py`, `cli/completeness_cmd.py` — so the predicate is one more consumer, not the first).
  - **Tokenize with `re.split(r"[^a-z0-9]+", haystack.lower())`** into a set, then return `bool(tokens & SECURITY_HINT_KEYWORDS)`.
  - **Exact-token match, not substring** — the load-bearing decision. A substring scan for `auth` matches `authoring`, `author`, `authored`; splitting file paths and titles on every non-alphanumeric boundary (so `src/auth/login.py` → `{src, auth, login, py}`, but `authoring.py` → `{authoring, py}`) makes the membership test reject `authoring` while accepting `auth`. This mirrors the captured "split-once / detector-not-validator" discipline: the scan is a name-source-agnostic *detector*, so it runs over derived and authored content alike, but it must not over-match a benign lookalike token.
  - **No imports of `Plan`/`Step`** — read `plan.title` / `plan.steps` / `step.all_files` by duck-typing so the predicate stays a cheap leaf and tests can pass a `SimpleNamespace`-style stub.
- **No cycle risk** — `security_audit.py` top-imports only persistence/fingerprint leaves and lazy-imports `review`/`launcher`; it imports nothing from `plan_tool.cli`. Both CLI consumers below import *from* it freely. **Implementation check (do not assume):** before adding the top-level `from plan_tool.security_audit import security_hint_is_relevant` in `authoring.py`, open the as-built `security_audit.py` (created in step 1, extended in steps 2/4) and confirm it has no `import plan_tool.cli` / `from plan_tool.cli …` statement at module scope — `security_audit.py` is not yet on disk when this detail is authored, so the no-back-import claim is a forward assertion. A back-import would make the new top-level `authoring.py` import a cycle; if one is found, push the offending `plan_tool.cli` import in `security_audit.py` into a lazy/function-local site (or import `security_hint_is_relevant` lazily in `authoring.py`) before wiring the emission gate.

### `plan_tool/cli/parser.py` — the global `--no-security-hint` flag

- **Add one argument in `make_base_parser`**, in the global-flag block (sibling of `--no-wait-on-rate-limit`):
  - `action="store_true"`, `dest="no_security_hint"`, default falsy.
  - Help: suppress the advisory `plan-tool security <name>` next-step pointer printed by `detail` / `completeness-audit`. As a base-parser global the flag must precede the subcommand (`plan-tool --no-security-hint detail <name>`), not trail it — word the help so it does not imply an end-of-command position.
- **Global, not per-subparser — the load-bearing wiring decision.** The pointer is emitted from two different command modules: `detail` (in `authoring.py`, in scope) and `completeness-audit` (whose subparser is built in `plan_tool/cli/completeness_cmd.py:register`, **out of scope**). A global flag on the shared base parser reaches both namespaces without editing `completeness_cmd.py`, and matches the existing precedent of broad authoring/experiment flags (`--prompt-mode`, `--backend`, `--model`) living on `make_base_parser`. Every other subcommand accepts it as a harmless no-op (only `cmd_detail` and `_persist_and_present_report` read it).
- **Consequence:** the top-level help usage line gains `[--no-security-hint]`, so the package-surface golden is regenerated (see *Beyond declared `files:`*).

### `plan_tool/cli/authoring.py` — gate the `detail` emission site

- **Wrap step 5's security pointer** inside the existing `if rc == 0 and wrote and not args.dry_run:` block, immediately after the review/run/jira `_print_next_steps("Next steps:", …)` call. Step 5 added the `_print_next_steps("Security check:", [(f"plan-tool security {args.name}", …)])` call as its own self-contained call (per the captured cross-step rule, so this gate wraps exactly that line and disturbs no sibling).
- **Gate condition** — emit only when:
  - `not getattr(args, "no_security_hint", False)`, **and**
  - `security_hint_is_relevant(plan)`, where `plan` is parsed from the on-disk plan via `parse_plan(path)` (`path` is already in scope from `resolve_plan_for_context`). `cmd_detail` has no parsed `Plan` at the tail — `generate_detail` returns per-step `results`, not the plan — so parse once here.
  - **Fail-soft on parse error** — wrap the `parse_plan(path)` + predicate in a local guard that treats any exception as "not relevant" (skip the hint). The plan was just authored against and parses, but the hint is advisory: a parse hiccup must never break the clean-run success tail.
- **Reads `getattr(args, "no_security_hint", False)`** (not bare `args.no_security_hint`) so component tests building partial namespaces stay green.

### `plan_tool/cli/completeness_phases.py` — gate both branches of `_persist_and_present_report`

- **`plan` and `args` are already parameters** of `_persist_and_present_report`, so no re-parse is needed (contrast `cmd_detail`).
- **Compute the verdict once**, before the `if iterate_enabled:` fork:
  - `show_security_hint = not getattr(args, "no_security_hint", False) and security_hint_is_relevant(plan)`.
- **Gate step 5's pointer in BOTH branches** — the function forks on iterate-vs-audit-only and never rejoins (captured two-branch rule): wrap the `_print_next_steps("Security check:", …)` call after `print(console_summary(...))` in the `if iterate_enabled:` branch, and the one after the grouped-report / `"saved to"` print in the `else:` branch. Editing one branch silently drops suppression for the other mode.
- **Add `from plan_tool.security_audit import security_hint_is_relevant`** body-local, next to the existing `from plan_tool.completeness_report import (...)` import (matches this file's body-local import convention; no cycle, per the leaf rationale above).
- **No change to `--json` or the grouped report** — the gate touches only the stderr `_print_next_steps` call. `_render_completeness_json` and `_render_grouped_report` are untouched, so headless `--json` callers and the grouped-report bytes are unaffected.

### Shared-logic audit

- **The keyword relevance scan is novel** — no existing function in `plan_tool/` scans plan title + step titles + file paths for keyword relevance. `plan_tool/create.py:extract_file_path_candidates` extracts path *candidates* from free text (different purpose, different output) and is left untouched.
- **`Step.all_files` (`plan_tool/schema.py`) is the single footprint accessor** — the predicate uses it rather than re-uniting `step.files` + `step.creates` by hand, so the gate's notion of "declared file paths" can never drift from the rest of the tool's.

## Tests

### Test-creation order (feature step)

This is a **feature** step — new behavior (the predicate, the flag, the two gated emissions). Enumerate and author every test below **with** the implementation; each must be green before the step is considered done.

**`tests/test_security_audit.py`** (pure predicate — no Claude, no I/O; pass `SimpleNamespace`-style plan/step stubs):

- `test_relevant_on_step_title_keyword` — a plan with `"authentication"` in a step title → `True`.
- `test_relevant_on_plan_title_keyword` — keyword only in `plan.title` (e.g. `"Password reset flow"`) → `True`.
- `test_relevant_on_declared_file_path_token` — keyword only in a step's `files` (e.g. `"src/auth/login.py"`) → `True` (tokens `auth`, `login`).
- `test_authoring_substring_not_matched` — a plan whose only near-match is `"authoring"`/`"author"` and no real keyword → `False` (proves exact-token, not substring — the load-bearing guard).
- `test_match_is_case_insensitive` — `"OAuth Token Exchange"` → `True`.
- `test_plain_plan_irrelevant` — title `"Add pagination"`, steps `"render list"` / files `["ui/list.tsx"]` → `False`.
- `test_scans_creates_not_only_files` — keyword only in a step's `creates` (via `all_files`) → `True`.

**`tests/cli/test_completeness_cmd.py`** (`TestPersistAndPresentReport`; capture stderr/stdout, stub the sidecar write so no disk audit fires):

- `test_security_hint_shown_when_relevant_audit_only` — relevant plan, `no_security_hint` false, `iterate_enabled=False` → `plan-tool security <name>` printed to stderr.
- `test_security_hint_shown_when_relevant_iterate` — same, `iterate_enabled=True` → pointer printed.
- `test_security_hint_suppressed_by_flag` — relevant plan, `args.no_security_hint=True` → no pointer (assert for both branches).
- `test_security_hint_hidden_when_irrelevant` — plain plan, flag false → no pointer (both branches).
- `test_grouped_report_unchanged_by_gate` — stdout grouped-report bytes identical with the gate hiding vs showing the pointer (gate touches only stderr).
- `test_no_security_hint_parses_on_completeness` — `plan_tool.cli.app.build_parser().parse_args(["--no-security-hint", "completeness-audit", "demo"])` sets `no_security_hint is True`; absent → `False`. The flag is global (on `make_base_parser`), so it must precede the subcommand — argparse rejects it after the subcommand.

**`tests/cli/test_authoring_cmds.py`** (drive `cmd_detail` with the detail orchestrator stubbed at the `plan_tool.cli.authoring.generate_detail` seam so no Claude fires; capture stderr):

- `test_detail_security_hint_shown_when_relevant` — clean wrote run on a relevant plan → pointer printed.
- `test_detail_security_hint_suppressed_by_flag` — `--no-security-hint` → no pointer.
- `test_detail_security_hint_hidden_when_irrelevant` — plain plan → no pointer.
- `test_detail_hint_fail_soft_on_parse_error` — stub `parse_plan` to raise → `cmd_detail` still returns 0 and prints no security pointer (advisory never breaks the success tail).

**Green-before-done gate:** every test above is green, and the conftest real-backend gate never fires (no test reaches a live `claude`/`codex` binary).

## Acceptance criteria

- `security_hint_is_relevant(plan)` returns `True` for a plan with any `SECURITY_HINT_KEYWORDS` token in its title, a step title, or a declared file path; `False` otherwise.
- `security_hint_is_relevant` returns `False` for a plan whose only near-match is `authoring`/`author` (exact-token, not substring).
- `security_hint_is_relevant` performs no Claude call and no disk I/O.
- `plan_tool.cli.app.build_parser().parse_args([...])` exposes `no_security_hint` (default `False`, `True` with a leading `--no-security-hint` before the subcommand, e.g. `["--no-security-hint", "detail", "demo"]` / `["--no-security-hint", "completeness-audit", "demo"]`) on both the `detail` and `completeness-audit` namespaces; as a global `make_base_parser` flag it precedes the subcommand and is rejected after it.
- A clean `detail` run on a security-relevant plan prints one `plan-tool security <name>` pointer to stderr; on a plain plan, or with `--no-security-hint`, it prints none.
- A `completeness-audit` run (both `--iterate` and audit-only) prints the pointer only when relevant and not suppressed; the `--json` payload and grouped-report stdout bytes are unchanged by the gate.
- `tests/cli/package_surface_help.golden.txt` is regenerated to include `[--no-security-hint]` and `tests/cli/test_package_surface.py` is green.
- All enumerated tests pass; the conftest real-backend gate does not fire.

## References

- [argparse — add_argument / parent parsers (Python docs)https: — `store_true`, `dest`, and where a flag on the base parser lands in the parsed namespace for every subcommand.
- [re — Regular expression operations (Python docs)https: — `re.split` boundary semantics for the exact-token tokenizer.
- [OWASP Top 10 (2021)https: — grounds the keyword vocabulary (broken access control, injection, cryptographic failures, secrets exposure).
- [CWE — Common Weakness Enumeration (MITRE)https: — standard weakness names (e.g. CWE-798 hardcoded credentials) backing tokens like `secret`/`credential`/`token`.

## Deferred

- **Claude-scored relevance** — a model judging whether a plan warrants a security pass. Out of scope: this gate is deliberately no-Claude/no-I/O so a wrong verdict costs nothing; a scored gate would re-introduce the cost the pointer-not-dimension design (step 5) avoids.
- **Per-keyword weighting / confidence thresholds** — the gate is a binary any-match. Weighting (e.g. `password` outranks `upload`) needs a scoring model and tuning data; not warranted for a one-line suggestion.
- **Suppressing the pointer at other surfaces** — only `detail` and `completeness-audit` emit it today (step 5). A future surface that adds the pointer also adds the `security_hint_is_relevant` + `no_security_hint` gate; not pre-wired here.
- **Consolidating the three keyword/relevance vocabularies** — `SECURITY_HINT_KEYWORDS` (this gate) vs the `plan_tool/prompts/security.md` checklist vocabulary vs any future per-step relevance scan. Single-sourcing them is a cross-module refactor `detail` cannot mint → route to reconcile.
