> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-tool-annotate-feedback.md`.
> Preserved here for history; do not edit.

# plan-tool `annotate` — process feedback

**Audience:** the `plan-tool` project maintainers (rupe120/plan-tool).
**Context:** Ran `plan-tool annotate ... --archive` across a real stale backlog of **30 untracked
implementation plans** in the example-app amplify repo to retire/iterate them. This is a living report —
updated as the batch runs — capturing where the process should change.

**Run shape (per plan):**
```
plan-tool annotate <plan>.md \
  --seed   docs/implementation-plans/plan-seeds/<stem>.seed.md \
  --report docs/implementation-plans/archive/<stem>.annotated.md \
  --archive
```
Single-pass, non-interactive, ~35s for a small plan, longer for large/well-grounded ones. Worked as
documented on the happy path.

---

## P1 — A single descriptive (non-actionable) section aborts the whole-plan annotate

**Severity:** High (data-loss-shaped: the plan produces *no* seed/report/archive — it is simply dropped).

**Observed:**
```
[14] FAIL 2-high-value-test-coverage ::
  error: annotate entry 'Bugs and Risks Surfaced During Analysis' is
  NOT-IMPLEMENTED but carries code_refs (contradictory verdict)
```

**Root cause:** The validator treats `NOT-IMPLEMENTED + code_refs` as a contradiction and hard-fails the
*entire* annotate. But that section ("Bugs and Risks Surfaced During Analysis") is **descriptive
analysis, not implementable scope** — it legitimately cites code (the bugs it found) while having nothing
to "implement". The IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED trichotomy has no bucket for
"observational / non-actionable" sections, so the classifier is forced into a verdict the validator then
rejects.

**Why it matters:** Plans routinely contain non-actionable prose — "Risks", "Background", "Findings",
"Open Questions", "Out of Scope". Any one of them can trip this and discard a 38 KB plan's entire
analysis. The failure is all-or-nothing.

**Update — confirmed intermittent:** a plain **re-run of the exact same command succeeded** (clean
classification, seed + report + archive all produced). So this verdict-vs-validator contradiction is
**LLM nondeterminism**, not a structural property of the plan. That strengthens fix #1: the validator
should never hard-abort on a transient contradiction — a built-in retry (the authoring family already
has checkpoint/resume) or graceful per-section degrade would have made this self-heal instead of
dropping the plan from a batch.

**Suggested fixes (any one helps; first is cheapest):**
1. **Degrade gracefully, don't abort.** On a contradictory verdict, emit a warning + still write the
   report/seed (mark that section `NEEDS-REVIEW`) rather than failing the whole run. A backlog sweep must
   be resilient to one bad section.
2. **Add a `DESCRIPTIVE` / `NON-ACTIONABLE` classification** for sections that are analysis, not work, so
   `code_refs` on them is valid and they're excluded from the carryover seed automatically.
3. **Relax the validator:** `NOT-IMPLEMENTED + code_refs` is only contradictory for *actionable* sections.
   Citing the code you inspected to conclude "not implemented" is normal evidence, not a contradiction.

---

## P2 — Confident verdicts emitted with near-zero grounding

**Severity:** Medium (silent unreliability — the verdict *looks* authoritative).

**Observed (grounded_files vs. coverage):**

| Plan | grounded_files | verdict |
|------|:---:|---|
| `1-partner-sftp-server-executive-summary` | **0** | 2 IMPLEMENTED · 1 NOT-IMPL |
| `2-labor-data-service-classification-api-diagrams` | **0** | 3 PARTIAL · 5 NOT-IMPL |
| `2-ai-chat-conversational-tone` | **1** | 17 NOT-IMPL · 10 low-conf |
| `2-achievement-triggers-jira-plan` | **1** | 10 NOT-IMPL |
| `2-cv-labor-data-service-structured-data` | **2** | 3 IMPLEMENTED · 3 PARTIAL |

A report with `grounded_files: 0` still emitted **2 IMPLEMENTED** sections — i.e. it claimed code exists
while grounding on zero files. There's a clear correlation: prose-heavy docs (executive summaries, jira
exports, diagram docs, vision/tone docs) ground poorly and then either over-claim IMPLEMENTED or
default-dump everything to NOT-IMPLEMENTED with a wall of low-confidence flags.

**Suggested fixes:**
1. **Grounding-floor guard:** when `grounded_files` is below a threshold (e.g. < 3), suppress confident
   IMPLEMENTED/PARTIAL verdicts and stamp a report-level banner: *"Low grounding (N files) — verdicts are
   speculative, verify before trusting."* The per-section low-confidence flag exists but there's no
   *report-level* trust signal.
2. **Surface `grounded_files` in the console summary line**, not just the report's HTML comment, so a
   batch operator sees which results to distrust without opening each file.
3. Consider **detecting non-plan doc types** (exec summary / diagrams / jira export) and short-circuiting
   with "not a code-bearing plan — archive without seed" instead of fabricating section verdicts.

---

## P3 — No batch mode for backlog sweeps

**Severity:** Medium (ergonomics; the documented use case is "a long stale backlog").

`annotate` takes exactly one file and there is no `--batch` / glob / directory form, so a backlog sweep
requires a hand-rolled shell loop (and hand-rolled failure tracking, summary extraction, and
seed/report routing). The tool's own guidance frames annotate as *the* backlog-draining workflow, so the
single-file-only constraint fights its primary purpose.

**Suggested:** `plan-tool annotate <dir-or-glob> --archive --seed-dir ... --report-dir ...` that loops,
continues past per-file failures (see P1), and prints a coverage + grounding summary table at the end.
A `--seed-dir` / `--report-dir` pair (vs. per-file `--seed`/`--report`) is the missing primitive.

---

## P5 — Grounding reads binary repo files → `ValueError: embedded null byte` crash

**Severity:** High (deterministic, unrecoverable hard crash + opaque traceback).

**Observed:**
```
[23] FAIL 3-bundle-size-optimization
plan-tool: unexpected error: ValueError: embedded null byte
  ... File ".../subprocess.py", line 1902, in _execute_child
      self.pid = _fork_exec(args, ...)
  ValueError: embedded null byte
```

**Root cause:** The crash is in `subprocess._execute_child` — annotate built an **argv that contains a
NUL byte** and `_fork_exec` rejects it. The **plan file is clean** (verified: `b'\x00'` count = 0, valid
UTF-8). This is the *bundle-size-optimization* plan, which references `dist/`, minified JS, source maps,
and ~14 MB of images — so annotate's grounding step almost certainly **read a binary asset** while
scanning the repo and then passed those bytes into a subprocess argument (e.g. a `grep`/`claude`
invocation seeded with grounded content). NUL-bearing binary content in argv = instant crash.

**Why it matters:** Any plan whose grounding surface overlaps build output, images, fonts, `.map`,
`.wasm`, lockfile blobs, etc. will hard-crash. It's deterministic (re-run reproduced it identically) and
the traceback gives no hint that "a binary file in your repo" is the cause.

**Suggested fixes:**
1. **Never feed file bytes into argv.** Pass grounded content via stdin / a temp file, not command-line
   arguments — argv has hard limits and NUL-intolerance.
2. **Skip/!detect binary files during grounding:** test for NUL in the first N bytes, or honor
   `.gitignore` / a text-extension allowlist, before reading a file as grounding context.
3. **Sanitize defensively:** strip NUL (and cap length) on any string crossing the subprocess boundary,
   and convert the raw `ValueError` into a clear message: *"grounding skipped binary file <path>"*.

**Workaround used here:** archived the plan manually and hand-wrote its seed from section headers
(`plan-seeds/3-bundle-size-optimization.seed.md` in the consuming repo), since the tool cannot process it.

---

## P6 — `--archive` silently no-ops on a name collision but reports success

**Severity:** Medium (false success → stale file left in the active set).

**Observed:** `2-ai-chat-deep-linking` had a *pre-existing* `archive/2-ai-chat-deep-linking.replaced.md`
(an older superseded stub). On `--archive`, annotate reported success and wrote the seed + report, but
the **original was left in place** in the active dir — the move to the already-occupied
`<stem>.replaced.md` target did not happen, yet nothing surfaced the collision. The operator only finds
out by noticing a "successful" plan still sitting in the source directory.

**Suggested fixes:**
1. **Fail loud or disambiguate** on target collision: either refuse with a clear error, or pick a
   non-colliding name (`<stem>.replaced.2.md`) — never report "archived" when no move occurred.
2. Make the archive move **atomic with the success report**: if the move is skipped, the run is not OK.

---

## P4 — Minor UX

- `--iterate` is accepted but inert on `annotate` (already documented as reserved). It's a footgun in a
  family where `create`/`detail` default `--iterate` ON; consider rejecting the flag outright on annotate
  so muscle-memory doesn't imply a convergence loop that never runs.
- `--archive` moves the source to `archive/<stem>.replaced.md` but the report defaults *beside the
  source* (now an archived location). Routing `--report` and `--seed` explicitly is required to get a
  clean layout; a documented "sweep layout" recipe (seed→plan-seeds/, report+original→archive/) would
  save everyone reinventing it.

---

## P7 — Provide a backlog status rollup so nobody hand-maintains one

**Severity:** Low (feature) — but high-leverage for adoption.

**Observed in the field:** the consuming repo carried a checked-in `implementation-plan-review.md` — a
hand-authored table (`Plan | Status: Not-Started/Partial/Completed | Notes`) plus a changelog of
README edits. It was **stale by construction**: stamped one date, wrong plan count, listing
since-archived/renamed plans, contradicted by the very `annotate` sweep this report documents. We deleted
it. The instinct that produced it is real: people want a single *"what's the state of the whole
backlog"* view, and in the absence of one from the tool, they hand-write a snapshot that immediately rots.

**`annotate` already computes the ground truth** (per-plan, per-section, code-grounded) — it's just
per-file and not aggregated. Surface it:
1. **`plan-tool list --status`** (or extend `sweep --report-only`) → a one-shot rollup table across all
   manifest + on-disk plans: name, IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED counts, grounded_files, last
   annotated date. Reads cached `*.annotated.md` where present; flags un-annotated plans.
2. Optionally `--format md` to emit the exact table a human would otherwise paste into a doc — but
   generated on demand from ground truth, never checked in as a snapshot.

This closes the loop with P3 (batch mode): sweep → annotate-all → status-rollup is the backlog-drain
trifecta, and it removes the temptation to keep a parallel hand-maintained status file.

---

## P8 — `jira` generator emits acceptance criteria that need a manual cleanup pass

**Severity:** Low-Medium (feature/quality) — observed via a downstream symptom.

**Observed in the field:** the consuming repo carried a 380-line hand-authored
`jira-story-acceptance-criteria-updates.md` whose entire job was to *fix the acceptance criteria* of
stories generated by `plan-tool jira` after they'd been pushed to Jira. Its recurring "rewrite
principles" are a clean spec for what good AC should be — and a list of what the generator currently
emits that shouldn't be a pass/fail gate:

- State **observable outcomes** (subscription fires, data correct, tests pass), not implementation steps.
- **Do not** use line numbers, import lists, exact call-site counts, repo-wide grep counts, or file-size
  caps (e.g. "&lt;120 lines") as acceptance criteria.
- Prefer **automated tests** over manual DevTools / dual-platform manual checks where CI can cover it.
- Keep exact AWS resource names / path literals in the **description**, not the AC, unless the story is
  explicitly an infra contract.
- For verification-only stories, separate **"done" (behavior verified)** from **"evidence recorded"**.

**Suggested:** encode these as generation rules in `plan-tool jira` (and/or a `jira --lint` that flags
line-number / grep-count / size-cap bullets). If the generator produced outcome-based AC, the manual
cleanup doc wouldn't need to exist. Note the limit: plan-tool emits exports *into the repo* and cannot
read *live* Jira, so the per-issue reconciliation itself stays a human/integration task — but better
generated AC shrinks it to near-zero.

---

## Healthy signals (works well)

- Well-grounded substantive plans classify accurately and richly: `1-vendor-sftp` (44 files),
  `2-ai-chat-deep-linking` (36), `1-labor-data-service-skills-selection-mvp` (19, with a useful 14-IMPL/14-PARTIAL
  split).
- The seed's **"Already implemented (done-context — do not re-plan)"** vs. **"Carryover scope (remaining
  work)"** split is exactly right for feeding `create --from-existing` without re-planning finished work.
- Per-section evidence strings (file + symbol + why) are concrete and verifiable, not hand-wavy.

---

## Run ledger (final)

- Total untracked plans processed: **30**
- Annotated OK: **29** (28 on the first batch pass + `2-high-value-test-coverage` on a clean retry)
- Hard-failed, unrecoverable: **1** (`3-bundle-size-optimization` — P5 binary null-byte crash; archived
  + hand-seeded manually)
- Transient failure that self-healed on retry: **1** (`2-high-value-test-coverage` — P1)
- Silent archive collision needing manual fix: **1** (`2-ai-chat-deep-linking` — P6)

### Failure-rate summary
- **2 / 30 (6.7%)** plans failed on the first automated pass; **1 / 30 (3.3%)** could not be processed by
  the tool at all. For an unattended backlog sweep, P1 (retry) and P5 (binary grounding) are the two that
  most need fixing — together they account for both first-pass failures.
