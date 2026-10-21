# Step 4 — Run the smell checks from `validate` and print advisory rationales before any Claude spend (rc reflects completion, never findings)

## Summary

Wire step 2's `plan_tool/review.py:collect_smell_findings` into `plan_tool/cli/inspect.py:cmd_validate` so a valid plan's two advisory smell findings (suppression-shape, self-referential) print right under the `OK:` verdict — the cheapest, fully no-Claude surface. The key decision: smells run **only on the valid path** (they need a parsed `Plan`; a schema-invalid plan returns before they could run, so every existing `INVALID:` path stays unchanged), and the smell count is **never compared against anything that returns a non-zero rc** — `--fail-on-findings` keeps flipping rc only on `INVALID`, never on a smell. Import `collect_smell_findings` body-locally inside `cmd_validate` so tests can patch `plan_tool.review.collect_smell_findings` (a domain-module attribute, not a cli global — honoring the file's split-proof convention) and reach the call. On green: a valid plan that trips a detector prints `OK:` plus an `advisory smell checks (does not affect exit code):` block of one bullet per finding and still exits 0, even under `--fail-on-findings`.

## Table of Contents

- [Why](#why) — what's missing and why `validate` is the right pre-Claude surface
- [Files (creates vs edits)](#files-creates-vs-edits) — the two declared files and their edits
- [Implementation](#implementation) — capture the parsed plan, run smells on the valid path, render advisories, keep rc tied to completion
- [Tests](#tests) — `cmd_validate` smell cases in `tests/cli/test_inspect_cmds.py`
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author tests with the code; green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — pydantic/stdlib docs relevant to this step
- [Deferred](#deferred) — out-of-scope items (status surfacing, second detector surface, byte-pinned rendering)

## Why

Step 2 ships the two smell detectors behind one public `plan_tool/review.py:collect_smell_findings` entry; step 3 (this step's sibling) surfaces them through `completeness-audit`. But `completeness-audit` is a heavier verb that also drives a conceptual Claude audit. The plan wants the smells to fire at author time "before any Claude spend" — and `validate` is exactly that surface: it is wholly no-Claude (schema check only), it is what an operator runs first, and it already parses the plan. Surfacing smells here means the suppression-shape / self-referential rationales reach the operator at the cheapest possible point, without waiting for a completeness run. **Recall is degraded pre-`detail`, by design of where `validate` sits in the `create → detail → audit` pipeline.** A freshly-created or hand-authored plan run through `validate` has no detail files yet, so the suppression detector's detail-body scan has nothing to read and runs **title-only** — near-zero recall on the motivating `type_impure` shape, whose suppressing purpose lives in its rationale prose, not its anodyne title. `validate` catches the detail-body suppression shape only once detail files exist; full-recall detail-body detection lands at `completeness-audit`, which runs post-`detail`. The hard constraint carried from the plan and the [[feedback_exit_code_convention]]: smells are advisory — they must not flip the exit code. `validate`'s rc already reflects completion (`OK`/`INVALID`), with `--fail-on-findings` flipping only on `INVALID`; this step must leave that contract intact and add the smells strictly alongside it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/inspect.py` — in `cmd_validate`: capture the parse result (`plan = parse_plan(path)`), and after the `OK:` print, body-local-import `collect_smell_findings` from `plan_tool.review`, call it with the parsed plan + `ctx.repo_root` + `plan_name=args.name`, and print an advisory block when it returns any findings. No change to the `except (ParseError, ValidationError)` arm or its `return 1 if … else 0`.
  - `tests/cli/test_inspect_cmds.py` — add smell-path cases to `TestCmdValidate` (advisory block renders, rc stays 0, `--fail-on-findings` does not flip on a smell, the invalid path never runs smells).

## Implementation

### `plan_tool/cli/inspect.py` — `cmd_validate`

**Capture the parsed plan.** `cmd_validate` currently calls `parse_plan(path)` inside the `try` and throws the result away (it only cared whether parsing raised). Change it to `plan = parse_plan(path)` so the valid-path code below has the `Plan` the detectors need. The `except (ParseError, ValidationError)` arm is unchanged — it still prints `INVALID:` and returns `1 if getattr(args, "fail_on_findings", False) else 0`.

**Run smells only after the success print, on the valid path.** Place the new logic after `print(f"OK: {path}")` and before `return 0`:
- The `INVALID:` arm returns *inside* the `except`, so it never reaches the smell block — the schema-invalid contract (and every `INVALID:` test) stays byte-for-byte the same.
- A schema-invalid plan also has no usable `Plan` to scan, so "valid-path only" is both the correct scope and the natural control flow.

**Body-local import of the entry, justified by test reach (primary) and cost (secondary).**
- Add `from plan_tool.review import collect_smell_findings` **inside** `cmd_validate`, not at module top.
- **Primary reason — monkeypatch reach under the file's split-proof convention.** `tests/cli/test_inspect_cmds.py`'s header forbids `monkeypatch.setattr` on any `plan_tool.cli` module global. A body-local import rebinds the name from `plan_tool.review` at call time, so a test patches `plan_tool.review.collect_smell_findings` (a domain-module attribute, allowed) and `cmd_validate` picks up the stub. A module-top `from … import collect_smell_findings` would bind the name into `plan_tool.cli.inspect`'s namespace, forcing tests to patch that cli global — exactly what the convention bans.
- **Secondary reason — keep the cheap inspection verbs cheap.** `cmd_list` / `cmd_status` / `cmd_root` live in the same module and must not pull in the large `plan_tool/review.py` on every `inspect` load; the body-local import fences `review` to the one verb that uses it.
- **No cycle to dodge here.** `plan_tool/review.py` imports no `plan_tool.cli` module, so there is no import cycle — do not cite cycle-breaking as the reason (it would be a false justification a later refactor could "correct").

**Call shape.** `collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)` — matches step 2's signature `collect_smell_findings(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]` and step 3's identical call. `ctx` is already in scope (`ctx = _load_context(args)`), and `ctx.repo_root` is the same attribute `cmd_list` reads. `plan_name=args.name` is only an id-minting namespace (via `review._make_rec_id`); `validate` does not consume the ids, so the exact value is irrelevant beyond stability.

**Render the advisories (advisory framing, stdout).** When the returned list is non-empty, print under the `OK:` line:
- A header line that names the block and states it is advisory, e.g. `  advisory smell checks (does not affect exit code):` — the `does not affect exit code` phrase is the operator's cue (and a stable test anchor).
- One bullet per finding: `    - {rec.severity.upper()}: {(rec.body or rec.title).strip()}` — same plain shape step 3 uses for the grouped report's `### Smells (advisory)` bullets (smells carry no `rec.anchor`, so render plain, not anchor-tagged).
- When the list is empty, print nothing extra — a clean valid plan still emits only `OK: {path}`, keeping `test_valid_plan_prints_ok_and_exits_0` green.
- Keep this on stdout (the same stream as the `OK:`/`INVALID:` verdict) so it travels with the verdict; a small module-private helper (e.g. `_print_smell_advisories(recs)`) is acceptable but optional — inline is fine and stays within the declared footprint.

**rc stays tied to completion — the structural guarantee.**
- `return 0` is unconditional after a successful parse, regardless of how many smells printed.
- The smell list is **never** passed to, or compared inside, any expression that produces the return code. `--fail-on-findings` is read only in the `except` arm (`INVALID`); it is not consulted on the valid path. So a smell can never flip rc, independent of its severity — the same structural-exclusion posture step 3 applies in completeness. State this in a one-line comment at the call site.

**Fail-soft is inherited, not re-added.** `collect_smell_findings` and its detectors are deterministic and fail-soft per step 2 (an absent/malformed `.plan-tool/config.json` self-referential set yields `[]`; the suppression scan reads the in-memory plan). Do **not** wrap the call in a defensive `try/except` — that would mask a real bug and duplicate step 2's contract.

### Cross-step contract (depends_on: 2)

- `collect_smell_findings`, `detect_suppression_shape`, and `detect_self_referential_features` **do not exist at HEAD** — step 2 introduces them in `plan_tool/review.py`. Before implementing, grep `plan_tool/review.py` for `collect_smell_findings`; confirm the name, arity, and that it returns `list[Recommendation]` with `severity`/`body`/`title` populated. If step 2's shipped signature diverged from `(plan, repo_root, *, plan_name)`, adapt the call.
- This is the second of `collect_smell_findings`'s two intended consumers (step 3's completeness layer is the first); both must call the one public entry rather than reaching for the individual detectors.

### Foundational logic / shared-location audit

- **Core behavior:** surface step 2's advisory smell findings on a no-Claude inspection verb without affecting rc.
- The only other surfacing site is step 3's `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` (populates `_DeterministicReport.smell_recs`). Both consume `collect_smell_findings`; there is no duplicated detection logic to consolidate — detection is single-sourced in `plan_tool/review.py` by step 2. No consolidation/refactor is owed.
- `validate` deliberately does **not** route smells through the deterministic battery `collect_deterministic_findings`; that collector feeds the `--iterate` apply loop, and smells must never reach `apply_finding`. Using `collect_smell_findings` directly keeps the advisory-only path intact.

## Tests

All cases in `tests/cli/test_inspect_cmds.py`, class `TestCmdValidate`, driven through `main(argv)` per the file's split-proof convention. Where a canned finding is needed, patch `plan_tool.review.collect_smell_findings` (the domain-module attribute the body-local import reads) — never a `plan_tool.cli.inspect` global.

- `test_valid_plan_with_no_smells_prints_ok_only` — a clean valid plan (the `registered_plan` demo) prints `OK:`, rc 0, and the output does **not** contain `advisory smell checks` (no detector trips, so no block).
- `test_valid_plan_with_smell_prints_advisory_rationale` — patch `collect_smell_findings` to return one `info`/`suppression-shape` `Recommendation`; assert stdout contains `advisory smell checks`, `does not affect exit code`, and the finding's body text; rc is 0.
- `test_smell_does_not_flip_rc_under_fail_on_findings` — same patched finding plus `--fail-on-findings`; assert rc is still 0 (smells are advisory; only `INVALID` flips). The key guarantee.
- `test_invalid_plan_skips_smell_checks` — schema-invalid plan **and** patch `collect_smell_findings` to raise; assert `validate` prints `INVALID:`, rc 0, and no exception escaped — proving the smell call never runs on the invalid path.
- `test_real_suppression_plan_trips_advisory` (integration, exercises step 2's real detector) — register a valid plan whose step title is a real gate-suppression (e.g. "Downgrade the mixed-step finding to advisory"); assert the advisory block renders and rc is 0, with no patch. Confirms the live wiring, not just the stub.

### Test-creation order (feature step)

This is a **feature** step — new surfacing behavior on `validate`. Author the five cases above alongside the `cmd_validate` edit:
- Cases 1–4 pin the contract (no-block-when-clean, block-when-smell, advisory-rc, invalid-path-skip) against a stub, independent of step 2's heuristic.
- Case 5 pins the real end-to-end wiring through step 2's detector (depends_on: 2).
- **Green-before-done gate:** every new test must pass, and the existing `TestCmdValidate` cases (`test_valid_plan_prints_ok_and_exits_0`, the two `INVALID`/`fail-on-findings` cases, the two `unparseable` cases) must stay green unchanged, before this step is finished.

## Acceptance criteria

- `cmd_validate` captures the parse result (`plan = parse_plan(path)`) and calls `collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)` only after the `OK:` print.
- A valid plan that trips a detector prints `OK:` followed by an advisory block containing `does not affect exit code` and one bullet per finding; a clean valid plan prints only `OK:`.
- Process rc is 0 for any valid plan regardless of smell count, **including under `--fail-on-findings`** (the smell list is never an input to the rc expression).
- A schema-invalid (or frontmatter-less) plan still prints `INVALID:` with the same rc as today (0 by default, 1 under `--fail-on-findings`), and `collect_smell_findings` is never called on that path.
- `collect_smell_findings` is imported body-locally inside `cmd_validate`; `tests/cli/test_inspect_cmds.py` patches `plan_tool.review.collect_smell_findings` (not a cli global) and the stub is reached.
- All new `TestCmdValidate` cases pass and all pre-existing `TestCmdValidate` cases stay green.

## References

- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — `parse_plan` raises `ValidationError` on the `INVALID:` path; confirms the valid path returns a fully validated `Plan` safe to hand to the detectors.
- [Python `dataclasses` documentation](https://docs.python.org/3/library/dataclasses.html) — `Recommendation` is a dataclass; reference for reading `rec.severity` / `rec.body` / `rec.title` when rendering the advisory bullets.

## Deferred

- **Surfacing smells from `status` (or other inspection verbs)** — out of scope; the plan names `validate` and `completeness-audit` as the two surfaces. `cmd_status` is a step-progress view, not a health check.
- **A `--no-smell-checks` flag (or any flag) on `validate`** — out of scope; the plan adds no new flag and notes that a future flag would make `docs/cli/` regen a separate owned step.
- **Byte-pinned rendering of the advisory block** — these tests assert substring presence and rc, not exact formatting; tighter output pinning can be added by reconcile if the block's shape needs to be frozen.
- **Unfalsifiable-feature smell check** — postponed at the plan level (needs an acceptance-criteria→feature tagging convention that does not exist yet); not a `validate` concern.
