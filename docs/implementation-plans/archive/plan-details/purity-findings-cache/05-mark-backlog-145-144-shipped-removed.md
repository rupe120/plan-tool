> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Remove BACKLOG #145 and #144 and reword the sibling entry that still points at them

## Summary

Delete the shipped `#145` (purity/quality cache) and `#144` (magnitude-threshold decision) entries from `BACKLOG.md` outright — this plan is their implementation, so per the doc's own "remove a feature's entry when it ships" rule they leave no shipped-status stub. Deleting `#144` *in full* is correct because `#144` ships in full here: not just its 0.5% Implementation/Tests section-diff floor but its complete frontmatter-change OR (`files:` via step 1's cache key, `change_type:`/`depends_on:` via step 2's stored prior values and step 4's grading) — so no part of the calibrated decision is dropped or left needing a follow-up entry. **Three** still-open siblings name `#145` and frame it as an unshipped prerequisite — `#103` (the MIXED-STEP purity-pass entry: "After #145…"), `#147` (parallelize purity scan: "land #145 first", "could ship as one plan"), and `#151` (the audit-grounding follow-up this very plan cites in its Out of scope: "**Relationship to #145:** Land / reconcile #145 first"). All three must have their `#145` references reworded in place to point at the now-shipped per-step purity cache, keeping each entry itself open and its own framing (e.g. `#147`'s DISCOURAGED note) intact — otherwise the `grep`-clean acceptance can't hold and `#151` would tell a reader to "land #145 first" for already-shipped work. Only the stale `#145`/`#144` *references* in these siblings are touched, never their substance or scope. The only file touched is `BACKLOG.md`. On green, `BACKLOG.md` contains no `#144` or `#145` token anywhere, `#103`/`#147`/`#151` still read correctly as open work, and no other entry is disturbed.

## Table of Contents

- [Why](#why) — the two entries are now implemented, so they must leave the forward-looking backlog
- [Input](#input) — what "the cache shipped" means, owned by steps 3 and 4
- [Files (creates vs edits)](#files-creates-vs-edits) — the single edited file and the three edits in it
- [Implementation](#implementation) — delete both entries, reword `#103`/`#147`/`#151`'s references, preserve spacing
- [Tests](#tests) — verification for a non-code doc edit
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [Deferred](#deferred) — what this step intentionally leaves alone

## Why

`BACKLOG.md` is the forward-looking backlog: its own "How to use it" section says to **remove a feature's entry when it ships**, with the implementation plan file as the historical record. This plan (`docs/implementation-plans/2-purity-findings-cache.md`) is exactly the implementation of `#145` (the per-step purity/quality cache) and of `#144`'s resolved magnitude-threshold decision (`#144`'s own text says "implementation folds into #145"). Once steps 3 and 4 land, both entries describe finished work and must leave the backlog, or they read as open work that's already done. Leaving them also strands the still-open `#147` entry, whose prose treats `#145` as a not-yet-shipped item to land first — misleading whoever picks up `#147` next. The plan's acceptance criteria already require this: "`BACKLOG.md`'s #144 and #145 entries are marked shipped/removed once the fix lands." This step is the plan's backlog-reconciliation bookkeeping — the seed was `#145`-derived, so carrying that reconciliation forward is part of the plan's contract.

## Input

This step reads the shipped outcome of its two dependencies, not a code contract — cite what landed, don't restate how:

- **Step 3 — the shared purity cache helper.** Step 3 routes the three purity call sites through one cache helper so an unchanged step skips the Claude call. That is the body of `#145`. Only remove `#145` once step 3 is actually at HEAD.
- **Step 4 — the completeness-audit miss-grading policy.** Step 4 implements `#144`'s resolved decision **in full** in the audit path: the 0.5% Implementation/Tests section-diff floor **and** the complete frontmatter-change OR (`files:`/`change_type:`/`depends_on:`, the latter two off step 2's stored prior values). Because the whole OR ships — not just the `files:` half — `#144` lands complete and can be deleted outright with no residual follow-up. Only remove `#144` once step 4 is actually at HEAD.
- **Limit on verifying this input:** there is no test or fingerprint that proves "the cache shipped." The signal is that steps 3 and 4 are present and green. Read the shipped code before deleting, so the reworded `#103`/`#147`/`#151` prose names what actually shipped (a per-step purity cache shared across `detail` and `completeness-audit`), not what the plan merely proposed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — delete two entries and reword three siblings:
    1. Delete the entire `#144` entry (section **C. Investigations / decision-making**), from its `**#144 — …DECIDED…**` header through its `- **Origin:**` bullet.
    2. Delete the entire `#145` entry (section **D. Process / hygiene**), from its `**#145 — Cache per-step purity/quality findings…**` header through its `- **Origin:**` bullet.
    3. Reword the `#145` references in **`#103`, `#147`, and `#151`** so they name the shipped purity cache instead of an open backlog number. Do not delete any of the three. (Verify at implementation time with `grep -n '#145' BACKLOG.md` that these are the only surviving entries that reference it — the `#144`-body references vanish with `#144`.)

## Implementation

The core change is one bookkeeping rule: **the shipped entries leave the backlog, and any still-open entry that pointed at them stops pointing at a number that no longer exists.** Grounded in the current file:

- **Delete `#144` in full — and it is genuinely full.** #144's whole calibrated decision ships (step 4: the section-diff floor plus the complete `files:`/`change_type:`/`depends_on:` OR), so outright removal drops nothing — there is no deferred remnant needing a follow-up entry. Its header is `**#144 — Decide a magnitude threshold (not exact-match) for recommending a per-step purity re-check after a non-`detail` edit — DECIDED (2026-07-17); implementation folds into #145**`, and it runs through a long `**Resolved decision (2026-07-17…)**` block to its closing `- **Origin:**` bullet. Remove the whole entry, header through Origin. It sits in section **C**, between the decision items above it and the `**#148 — …**` entry below it — leave `#148` and every other C entry untouched.
- **Delete `#145` in full.** Its header is `**#145 — Cache per-step purity/quality findings by detail-file fingerprint; share the cache between `detail`'s own sweep and standalone `completeness-audit`**`, running through its `- **Origin:**` bullet. It sits in section **D**, directly above the `**#147 — Parallelize the per-step purity scan…**` entry — remove `#145` and stop; do not touch `#147`'s own content except the rewording below.
- **Reword the `#145` references in `#103`, `#147`, and `#151`; keep all three open.** All three are still-open entries that survive; each frames `#145` as a pending item to land first, which goes stale the moment `#145` is deleted. Reword each `#145` reference to name the **shipped per-step purity cache** (e.g. "the per-step purity cache that already cache-skips unchanged steps") rather than the number, keeping every sentence's meaning by changing only tense/reference:
  - **`#147`** (parallelize purity scan) — three places: its **Policy note** ("land #145 (cache-skip unchanged steps) so the serial loop simply runs fewer calls. If, after #145, per-step purity is *still* the serial bottleneck…"), its **"Why (and how it relates to #145)"** bullet (the header plus "#145 cuts the *number* of purity calls…", "#145 skips the unchanged steps and this parallelizes…"), and its **Dependencies** bullet ("pairs naturally with #145 … — could ship as one plan"). "Land #145 first" becomes "the shipped purity cache already cut the unchanged-step calls; if per-step purity is *still* the bottleneck…".
  - **`#103`** (MIXED-STEP purity pass) — its "After #145, prefer zero Claude on that path" reference: reword to "with the shipped purity cache, that path already prefers zero Claude…".
  - **`#151`** (audit-grounding follow-up — *this plan cites it in its own Out of scope*) — its "**Relationship to #145:** Land / reconcile #145 first" and the surrounding "#145's intended shape" / "after #145" references: reword to name the shipped cache ("with the purity cache shipped, this collapses to a short verification that the discard path is gone"), so it no longer tells a reader to land already-shipped work.

  Constraints that are **not** free to vary:
  - Each of `#103`/`#147`/`#151` stays open, and its own framing (e.g. `#147`'s DISCOURAGED / last-resort note, `#151`'s scope) stays intact — only the `#145`-as-future-item reference changes. Do **not** alter these entries' substance or scope (the plan's Out-of-scope leaves `#103`'s and `#151`'s own work alone; this touches only their stale reference).
  - Do not invent a replacement backlog number for the shipped cache. Point at the feature by name, not a `#`-number that resolves to nothing.
  - After the rewording, no `#145` (and no `#144`) token remains anywhere in the file.

- **Preserve the blank-line spacing at both removal seams.** Entries are separated by a single blank line. When `#144` and `#145` are cut, leave exactly one blank line between the entries that become adjacent (the C entry above `#148`; `#147`'s new top neighbor). Nothing in the repo parses `BACKLOG.md`, so a spacing slip produces no test failure — the diff is the only check.

**Rejected alternative:** leaving a "shipped"-status stub for `#144`/`#145` (title + a "done in plan 2" line). The doc's convention is outright removal with the plan file as history, matching how prior shipped entries were closed — a stub falls outside that convention and rots.

This step's foundational logic — "remove the shipped entry AND reword still-open siblings that reference it" — is a documentation rule, not code, so there is no parallel call site elsewhere in the app to consolidate. The same-file instances of the pattern are the `#103`/`#147`/`#151` rewordings, already in scope above.

## Tests

### Verification (non-code step)

This step changes no production code — there are no unit tests. Verify the artifact edits instead:

- `grep -nE '#14[45]' BACKLOG.md` — returns nothing (both entries gone, `#147`'s references reworded off the numbers).
- `grep -n '#147' BACKLOG.md` still finds the `#147` entry, and reading it shows it is still open, still DISCOURAGED, and now names the shipped purity cache rather than "land #145 first".
- Read the section-**C** seam where `#144` was and the section-**D** seam where `#145` was: exactly one blank line between the now-adjacent entries, and the neighbors (`#148`, `#147`, the C entry above `#144`) are byte-for-byte unchanged except the intended `#147` rewording.
- Confirm steps 3 and 4 are actually at HEAD before treating the removal as valid (the entries describe shipped work, so their removal is only correct once the work shipped).
- `uv run pytest -m "not integration" tests/ -q` still passes — a `BACKLOG.md`-only edit must not perturb any suite.

## Acceptance criteria

- `grep -E '#14[45]' BACKLOG.md` returns no matches.
- The `**#144 — …**` and `**#145 — …**` entry headers are both absent from `BACKLOG.md`.
- The `#147` entry is still present, still marked DISCOURAGED / last-resort, and its Policy-note, "Why (…relates to #145)", and Dependencies bullets read correctly with `#145` replaced by a name for the shipped purity cache.
- No other backlog entry (`#148`, `#133`, and the C/D neighbors of the removed entries) is changed.
- One blank line separates the entries left adjacent by each removal.
- `uv run pytest -m "not integration" tests/ -q` passes unchanged.

## Deferred

- Changing the *substance or scope* of `BACKLOG.md` `#133`, `#103`, `#115`, `#147`, or `#151` — those are separate open items this plan leaves alone (see the plan's `## Out of scope`). This step touches only their stale `#145`/`#144` *references* (in `#103`/`#147`/`#151`), rewording them to name the shipped cache; their own work stays open and untouched. `#133`/`#115` carry no `#145` reference, so they are not edited at all.
- Any change to the plan file's own `status:` frontmatter (`docs/implementation-plans/2-purity-findings-cache.md`) — the plan-status transition is owned by the run/execution mechanics, not this backlog edit, and that file is not in this step's `files:` list.
- Editing `BUG_BACKLOG.md` — neither `#144` nor `#145` lives there and nothing in them is a bug entry; no cross-file bookkeeping is implied.
