# Row-linked prose amendments in version comparison — code review ledger

| Field | Value |
| --- | --- |
| Change | `roadmap --compare` reports candidate row-linked prose amendments (BUG_BACKLOG "Version comparison omits row-linked candidate prose amendments") |
| Branch | `run/roadmap-candidate-row-prose-amendments` |
| Review range | `56ab19db..e81ec269` (pass 1 `3c355c63`; fixes `5c650a40`, `54c143af`, `970ea924`, `e81ec269`) |
| Reviewer | headless `claude -p` session, report-only (`.tmp/prose-amendments-code-review-1.stream.log`) |
| Disposition | converged after pass 5 (see Convergence status) |

## Settled decisions (hand to each reviewer)

- Patch output stays a byte-faithful Git patch; no renderer-added metadata.
- Binding rule (from the backlog entry): amendments bind only when the target is a
  stored candidate whose **direct** predecessor is the selected base. Any other
  candidate/base pair reports `not-directly-bound`; binding is never inferred from
  changed bytes. Deliberately not a multi-hop chain walk.
- Outcomes: `bound` (possibly empty), `not-applicable`, `not-directly-bound`.
- Malformed or unbindable candidate evidence refuses the comparison.

## Review pass 1 — /code-review (sonnet, headless), 2026-09-29

Scope: commit `3c355c63`. Method: read-only; the reviewer did not run the suite.

### 1. Chain walk binds across many hops, contrary to the entry's direct-predecessor rule — medium
`plan_tool/roadmap_compare_run.py:129`. The commit's multi-hop test and
`ROADMAP_FORMAT.md` pinned the broader behavior.
**Disposition:** fixed (pass-1 fix commit) — replaced the walk with a single
direct-predecessor check; `ROADMAP_FORMAT.md` and its test now state the entry's rule.
This overrides the multi-hop wording committed in `3c355c63`, in favor of the spec.

### 2. Fragments from a row added and later removed across hops would still be reported — medium, plausible
`plan_tool/roadmap_compare_run.py:141`.
**Disposition:** fixed — removed with finding 1 (single hop cannot reconcile against later hops).

### 3. Non-ancestor case validated every candidate to the root before answering — low
`plan_tool/roadmap_compare_run.py:140`.
**Disposition:** fixed — removed with finding 1; a non-direct pair loads only the target candidate.

### 4. Verification cases from the entry lacked tests — medium
`tests/test_roadmap_compare_run.py`.
**Disposition:** fixed — tests now cover direct binding with ordering, non-adjacent,
no-predecessor, base-is-the-candidate, row-only candidate (`bound`, empty), working/root/no-base
targets loading no candidate evidence, and malformed evidence refusing `run_roadmap_comparison`.
Verified by mutation: disabling the predecessor check turns 3 tests red. The cycle-guard
cases are gone with the walk. Raw-patch faithfulness is pinned by the existing renderer tests
(`render_patch_comparison` returns the captured patch unchanged).

### 5. Outcome meanings undocumented; card escapes multi-line fragments — low
`plan_tool/roadmap_compare_render.py:53`.
**Disposition:** fixed (docs) — `ROADMAP_FORMAT.md` and `docs/reference/commands.md` define
each outcome. Card JSON-quoting is deliberate (one line per item); JSON output carries the
exact fragment, and the format doc says so.

## Review pass 2 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..5c650a40` (whole feature). Method: read-only; the reviewer ran the three
comparison test files (52 passed) and checked binding, refusal, patch isolation, renderers,
and generated docs.

### 6. `docs/ARCHITECTURE.md` read-only import-graph claim is now false — medium (docs)
`docs/ARCHITECTURE.md:300-311`. `roadmap_compare_run.py` imports `roadmap_candidate_run`, which
imports writer-layer modules. Verified against the imports (`roadmap_revision_publish`,
`roadmap_feedback_ledger`, `shell`, `fileio`, `RunLogWriter`).
**Disposition:** fixed (pass-2 fix commit) — the section names the second edge and the binding
rule; the extraction (moving the loader into a read-only leaf) is **tracked BACKLOG #406**,
deliberately not taken here (out of scope, per the consolidation-finding rule).

### 7. `CAPABILITIES.md` `--compare` entry omits the new evidence — low
`CAPABILITIES.md:54-58`. **Disposition:** fixed — clause added, sibling of the other three docs.

### 8. Full candidate validation runs for a `not-directly-bound` pair — low
`plan_tool/roadmap_compare_run.py:131-141`. **Disposition:** declined — validating the stored
candidate before answering is what makes "malformed evidence refuses" hold on every candidate
target; a cheap-predecessor-first read would silently let malformed evidence through for
non-adjacent pairs. Cost is one candidate load per comparison; no correctness effect.

## Review pass 3 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..54c143af` (whole feature, probing the pass-1/2 fixes). Method: read-only; the
reviewer ran 685 comparison and CLI tests. No regression from the pass-1/2 fixes.

### 9. A candidate with no stored operation evidence is reported `bound` with an empty list — medium
`plan_tool/roadmap_compare_run.py:143`. Verified: `normalized_operations` is `None` for
selector-era and pre-route batch candidates (`roadmap_candidate_run.py:260,318,947`), and
`candidate_prose_amendment_diffs(None)` returns `()`. That rendered "admitted none" for
"unknown", breaking the never-inferred invariant.
**Disposition:** fixed (pass-3 fix commit) — new explicit outcome `no-operation-evidence`;
documented in `ROADMAP_FORMAT.md`, `docs/reference/commands.md`, `docs/how-to/roadmap.md`,
`CAPABILITIES.md`, `docs/ARCHITECTURE.md`. Unit test pins it; verified by mutation (removing the
guard turns it red).

### 10. Binding tests stub the loader; no end-to-end case with a real stored candidate — low
`tests/test_roadmap_compare_run.py:98-113`. **Disposition:** fixed — 
`test_comparison_binds_a_real_stored_candidates_prose_amendment_to_its_root` (in
`tests/test_roadmap_candidate_run.py`, where the stored-candidate fixtures live) stores a real
prose-bearing batch candidate and compares its root to it through the real loader; verified by
mutation (emptying the projection turns it red). A real legacy (`None`-evidence) candidate is
covered by the unit stub only: the shape (`normalized_operations=None`) is the field's real
default, and no fixture stores a pre-route candidate.

### 11. "Empty collection means admitted none" overstated what an empty result proves — low (docs)
`ROADMAP_FORMAT.md`. **Disposition:** fixed with finding 9 — the wording now scopes it to the
candidate's stored operations.

## Review pass 4 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..970ea924`. Method: read-only; the reviewer ran 89 tests and probed the full
base/target kind matrix and the never-inferred invariant. Both clean; no correctness findings.

### 12. Shipped BUG_BACKLOG entry still present — medium (bookkeeping)
`BUG_BACKLOG.md:1190`. **Disposition:** fixed — entry removed (fully shipped; the loader-edge
remainder is tracked as BACKLOG #406). Provenance: Integration Group 3 compliance-boundary candidate
review, 2026-09-29.

### 13. `commands.md` / `how-to/roadmap.md` called `no-operation-evidence` an "other pair" — low (docs)
**Disposition:** fixed — both reworded: the directly bound no-evidence candidate is named
separately from the `not-applicable` / `not-directly-bound` pairs.

### 14. No drift guard tying the outcome vocabulary to the docs — low (tests)
**Disposition:** fixed —
`test_every_prose_amendment_outcome_is_named_in_each_comparison_guide` reads the `Literal` and
requires every outcome in all five guides. It immediately caught two real gaps (`bound` missing
from `commands.md` and `how-to/roadmap.md`), fixed; verified by mutation on `ARCHITECTURE.md`.
A cosmetic over-long line in `docs/ARCHITECTURE.md` is deliberately left unwrapped.

## Review pass 5 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..e81ec269`, probing the pass-3/4 fixes. Method: read-only; 295 focused and 4687
wider tests passed. **Clean: no correctness, docs, or bookkeeping findings.** Two cosmetic ledger
points (header range, a test's file location) were corrected in this ledger.

## Convergence status

**Converged — low-yield then clean.** Pass 1: 5 findings (3 medium). Pass 2: 3 (no correctness
bugs). Pass 3: 3 (1 medium correctness). Pass 4: 3 (bookkeeping and low docs/tests, no correctness).
Pass 5: clean. Two consecutive passes (4, 5) were low-yield/clean, so the loop stops.

Deliberately not done: no push, no PR (not requested). Tracked follow-up: BACKLOG #406 (moving the
stored-candidate loader into a read-only leaf). Declined: finding 8. Left: one over-long line in
`docs/ARCHITECTURE.md`.
