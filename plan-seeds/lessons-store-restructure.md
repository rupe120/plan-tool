# Plan seed: restructure the general-lessons store

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing .agents/skills/plan-tool/plan-seeds/lessons-store-restructure.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition. The author then runs
`plan-tool detail` per step to flesh the plan out.

---

## Goal

Promote the tool's general-lessons store
(`.agents/skills/plan-tool/lessons/general.md`) from a single
append-only Markdown bullet file into a structured store that
supports per-surface sectioning, tag-based retrieval, and
command-aware prompt injection. Optimize for **future-Claude reading
at create/detail/review time**, not for human browsing.

Current state: the file is 467 bullets / ~400KB. `lessons.py` injects
only the first 6KB into prompts (`_MAX_INJECT_BYTES = 6144`),
head-truncated — so ~98% of the captured context is dead weight and
the slice future-Claude sees is whatever happened to land first in
plan-authoring order, not what's relevant to the current command.

## Context already in place (pre-this-plan)

Three forward-compatible primitives have already landed and are
assumed by the steps below:

1. **`surface` + `trigger` fields on `LessonEntry`.** Extraction
   prompts (`prompts/extract-lessons-{detail,review}.md`) emit these
   fields; `_coerce_entries` accepts them; `LessonEntry.render()`
   renders an inline `` `[surface]` `` prefix when set.
2. **Citations JSONL sidecar.** New writes stamp `added` / `source`
   into `general-citations.jsonl` (sibling of `general.md`) instead
   of an inline `<sub>` line. Bullets are now denser.
3. **`find_lesson_equivalences` primitive.** Claude-backed dedup /
   conflict-detection lives in `lessons.py`. The matching CLI
   wrapper (`cmd_lessons_consolidate`) is **not yet wired** in
   `cli.py` — that's step 5 below.

## Surface vocabulary (load-bearing for this plan)

The plan's routing rules depend on a fixed five-surface vocabulary.
**Do not re-litigate this list during create or detail** — if the
plan decides it's wrong, push back to the user before redesigning,
because the prompts, the `LESSON_SURFACES` constant, and the
existing tags on new bullets all assume this exact set.

The list is a **hybrid** — three command-aligned, two
content-aligned — chosen because it matches both (a) where the
existing 467-bullet corpus actually clusters and (b) the three
commands that consume lessons today (`create`, `detail`, `review`).

| Surface | Aligned to | Why it earns its slot |
|---|---|---|
| `create-heuristic` | `create.py` command | Heuristics for what `plan-tool create` should propose (file lists, complexity floors, `depends_on` propagation). Dominant cluster: ~80+ "`files: []` is wrong for X" bullets. |
| `detail-authoring` | `detail.py` command (covers `detail.md` + `detail-quality.md`) | Rules for what `plan-tool detail` should produce (acceptance-criteria shape, sibling-template citation, Deferred bullet patterns, file:line anchoring). Folds the two detail prompts because they critique the same artifact. |
| `review-heuristic` | `review.py` command | Rules for what `plan-tool review` should flag, suppress, or roll up (single-token false positives, stub-plan rollup, sentinel handling). Small but distinctive cluster. |
| `cross-step` | content cluster | Handoff rules between steps (deferred-bullet contracts, stub-replacement obligations, frozen-artifact diff invariants, citing prior-step placeholders by file:line). Applies during **both** detail AND review; forcing into one command's bucket loses the cross-cutting signal. |
| `domain-shape` | content cluster | Step-shape classification (UI-feature, schema-definition, infra-wiring, migration, operability, retention/policy) and the files/complexity/test patterns each shape implies. Applies during create (skeleton + complexity floor), detail (mirror conventions), and review (shape-vs-content mismatches). Most cross-cutting bullets in the corpus. |

### Why not a different cut

- **Not 1:1 with every plan-tool subcommand.** Only `create`,
  `detail`, and `review` inject `${lessons_block}` into a prompt
  today (verified by grep). Subcommands like `reformat`, `split`,
  `iterate`, `reconcile`, `completeness`, `jira`, `run`, `optimize`,
  `check`, `document`, and `lessons consolidate` either run
  deterministically or consume lessons indirectly via the three
  command-aligned surfaces above. Adding surfaces for non-consuming
  commands inflates the vocabulary without changing routing.

- **Not pure command-aligned.** Roughly 30% of bullets in the
  existing corpus are genuinely cross-cutting. A rule like "step N+1
  must enumerate the stub locations left by step N" applies during
  detail AND review; classifying it as one or the other
  miscategorizes and the loader has to undo.

- **Not pure content-aligned.** The future routing rule is "which
  command is running", so a content-only taxonomy would require a
  separate command→content mapping table to bridge the gap — added
  indirection without compensating flexibility.

### When to add a surface (out of scope for this plan, but recorded)

- A new lesson-consuming prompt lands, AND it has accumulated ≥3
  captured lessons that don't fit any existing surface. OR
- A content cluster grows past ~30 bullets and doesn't fit
  `cross-step` or `domain-shape`.

Adding a surface also requires updating the two
`extract-lessons-*` prompts and the `LESSON_SURFACES` tuple — one
of the few load-bearing cross-file invariants in the tool.

## Scope of work

1. **Pick the structured on-disk format for general lessons.** Two
   candidates to evaluate in the detail step: (a) single YAML file
   with one entry per record; (b) YAML index + Markdown-per-surface
   bodies. Decide on legibility-for-humans vs. parse-cost-for-tooling.
   Lock the choice in step 1 so downstream steps depend on it.
   Project lessons (`.plan-tool/lessons/project.md`) keep today's
   flat-Markdown shape — out of scope for this plan.

2. **Migrate the existing 467 bullets in `general.md` into the
   chosen format.** Hand-tag `surface` for each bullet
   (LLM-assisted classification is fine but a human gate is
   required because tags drive injection). Carry forward existing
   source citations from inline `<sub>...</sub>` lines into the
   citations sidecar (record-per-bullet, keyed by `_rule_hash`).
   Preserve every bullet verbatim in the `rule` field; do not
   collapse near-duplicates in this step.

3. **Refactor `lessons.py:load_lessons` to take
   `surfaces: Iterable[str] = ()`.** Returns a `LessonsBundle`
   filtered to the requested surfaces (empty tuple = all, for
   back-compat). Replace `_MAX_INJECT_BYTES` head-truncation with
   per-section overflow that allocates a fair share of the budget
   per requested surface and biases overflow toward shorter,
   higher-density rules (no `why` / no `example` first). Add a
   short top-of-block index line listing surfaces and bullet counts
   actually injected. Maintain the existing
   `render_lessons_block` framing contract.

4. **Update the three call sites to pass surface filters:**
   - `create.py` callers → `surfaces=["create-heuristic",
     "domain-shape"]`
   - `detail.py` callers → `surfaces=["detail-authoring",
     "cross-step", "domain-shape"]`
   - `review.py` callers → `surfaces=["review-heuristic",
     "cross-step"]`
   Land the surface lists as one module-level constant
   per command so future commands don't drift.

5. **Wire `cmd_lessons_consolidate` in `cli.py`** (the missing step 2
   of the prior `lessons-consolidate-and-dedup` plan). Surface-scoped:
   `--surface create-heuristic` or `--all`. Uses the existing
   `find_lesson_equivalences` primitive. Diff-by-default, `--apply`
   to write, headless-safe on non-TTY. Writes are section-aware.

6. **Add `cmd_lessons_promote` in `cli.py`.** Different from
   consolidate: takes a cluster of ≥3 bullets in one surface that
   share a rule signature (LLM-judged), asks claude to produce a
   single generalized header, and replaces the cluster with the
   header + a one-line evidence list of short refs. Diff-by-default,
   `--apply`, `--surface` scope. Captures the "8 bullets all saying
   `files:[]` is wrong on type X → one rule + 8 ref tokens" pattern
   that the existing corpus has.

7. **Add a section-aware writer for new entries.** `append_lessons`
   gains a `surface` parameter (already on the entries); the writer
   locates the matching section block and inserts inside it,
   regenerating the top-of-file index. Keep the writer
   single-threaded and brain-dead: lock-free, last-write-wins.
   Race tolerance is acceptable because details/reviews run
   sequentially in practice. Document this explicitly in the module
   docstring.

8. **Tests.** Unit coverage for: surface filtering in `load_lessons`;
   per-section overflow allocation; section-aware writer round-trip;
   citation-sidecar parity with rule hash; `consolidate` + `promote`
   CLI surfaces; the `surface`-routing constants on each command.
   Migrate any existing test fixtures that embed the old flat
   format.

9. **README + RUNBOOK updates.** Document the new layout, the
   surfaces controlled vocabulary (with the rationale section
   above), the two new CLI commands, and the recommended cadence
   for running consolidate / promote (e.g., after every N appends
   or before any release).

## Non-goals

- No changes to `project.md` (project-specific lessons) — keeps the
  flat append-only shape so codebase-specific lessons don't pay the
  migration cost.
- No `docs/explanations/lessons-learned.md` (dev-journal) changes — different file,
  different audience.
- No automated promotion / consolidation in `detail` or `review`
  runs — both stay manual CLI invocations (preserves the
  token-preservation invariant in `docs/explanations/lessons-learned.md` Lesson 2).
- No backward-compat shim for the old Markdown bullet format after
  migration — the file is rewritten in place and the old format is
  gone.
- No new surfaces added in this plan. The list is fixed at the five
  above; if a need surfaces during the migration step (step 2), the
  plan halts and the user decides whether to expand the vocabulary
  before resuming.

## Acceptance criteria (plan-level)

- `plan-tool detail` on any step injects a lessons block that is
  ≤6KB and contains only `detail-authoring`, `cross-step`,
  `domain-shape` surfaces.
- `plan-tool create` and `plan-tool review` do the analogous
  filtering with their declared surface lists.
- `general.md` (or its replacement) is parseable by the loader with
  no Markdown-regex heuristics; the `surface` tag is a first-class
  field.
- `plan-tool lessons consolidate --surface create-heuristic`
  produces a diff and exits 0 on an empty diff.
- `plan-tool lessons promote --surface detail-authoring` identifies
  at least one cluster on today's bullets (the `files:[]` family is
  a known target) and produces a diff collapsing it.
- Round-trip: append a new lesson via `plan-tool detail`, see it
  land in the correct surface section, and see it injected into the
  next matching `plan-tool detail` call.

## Risks

- **Section-aware writes lose the brain-dead-EOF-append
  invariant.** Document race tolerance explicitly; do not introduce
  file locking. The current writer is robust because it's stupid;
  the new writer must stay nearly as stupid.
- **Hand-tagging 467 bullets is the largest single chunk of work**
  and should be its own step. LLM-assisted classification is fine,
  but expect ~5–10% manual override.
- **A wrong surface taxonomy locks in the wrong injection axes.**
  This plan's surface list is already fixed (see above); step 1's
  format-choice work should not relitigate the surfaces themselves.
- **Migration is destructive** — once the old format is gone, the
  citations sidecar is the only audit trail. Step 2 must back up
  `general.md` before rewriting.

## References

- `plan_tool/lessons.py` — current lesson loading, rendering, and append seams.
- `docs/explanations/lessons-learned.md` — distinct development-journal contract that remains
  outside the general-lessons migration.
- `TESTING.md` — no-real-backend test convention for Claude-backed lesson
  equivalence checks.
