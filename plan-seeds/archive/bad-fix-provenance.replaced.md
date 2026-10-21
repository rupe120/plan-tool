> **Withdrawn 2026-08-19**: this seed fed a plan whose premise the plan-level
> review rejected. The withdrawn plan is preserved at
> `docs/implementation-plans/archive/2-bad-fix-provenance.withdrawn.2.md`.
> Preserve this source for history; do not edit or re-seed it.

# Plan seed: bad-fix provenance (#231)

```
plan-tool create bad-fix-provenance \
  --from-existing plan-seeds/bad-fix-provenance.md --iterate
```

Backlog source: **#231**. Mechanism settled 2026-08-11 (BACKLOG +
`.tmp/backlog-231-provenance-mechanism.md` + `.tmp/convergence-arc.md`
§ Stage 3 product settlements). When this ships, update `#231` (remove
shipped scope / mark plan-authored while pending) and refresh the
readiness lens that still lists `#231` as decision-first theoretical.
Arc Stage 3 (`impact_recurrence` / `edit_drift`) already shipped — this
plan supplies the missing apply→finding provenance those advisories
cannot claim as causation, and is the gate for any future *hard*
edit-drift exit (not in this Outcome).

---

## Outcome

A same-issue recurrence with an intervening apply/decline annotation
surfaces as a recommend-only bad-fix advisory; identity alone stays
non-causal.

## Product shape (not the intent)

`plan-tool convergence` (and completeness iterate stderr when evidence
is already loaded) prints that advisory. Ship writer-first: shared
remedy-note on every apply path including hand-apply, then the
identity × note diagnostic. No iterate `stop_reason`, exit-code flip,
plan mutation, or second provenance store.

## Settled decisions (plan must not re-litigate)

1. **Same-issue identity** — ordered tiers; first decisive wins. Prefer
   extending / sharing helpers with `_matches`, not a parallel
   full-body matcher. Do **not** use raw Claude prose similarity,
   embeddings, or token-overlap on full issue writeups.

   | Priority | Signal |
   |---|---|
   | 0 (fast path) | Equal finding `id` when both present |
   | 1 | Equal `anchor` (`[anchor-slug]`) when both present |
   | 2 | Equal normalized issue skeleton (`_normalize_audit_fingerprint` / body skeleton when no anchor) |
   | 3 | Title / existing `_matches` tier-3 fuzzy title |

   Finding `id` churns when wording drifts — never the *only* identity.

2. **Intervening remedy note** — every path that lands or declines a
   finding writes a durable sidecar `annotations[rec_id]` note:
   finding identity + outcome (`applied` / deliberate decline). Reuse
   existing `Annotation` shape (`status` + `note`; decline =
   `status=skip` with empty `halt_reason`). One shared writer helper;
   walk **and** hand-apply both call it. Do not invent a second store.

3. **Hand-apply surface** — Claude-session / operator hand-apply today
   Edits prose and writes no annotation (`DATA_CONTRACT.md` still says
   only the interactive walk populates them; parallel
   `completeness-apply` already persists — keep that, route it through
   the shared writer). Add a thin **record** CLI (completeness family)
   that writes `applied` / deliberate-decline annotations onto a saved
   completeness report by rec id (and/or anchor), so the default
   hand-apply path can leave durable notes without running the apply
   walk. Directives / CLAUDE.md hand-apply recipe must name that
   command.

4. **Render** — identity match **and** intervening note →
   recommend-only bad-fix advisory. Identity without note → no
   bad-fix advisory (existing recurrence/edit-drift behavior
   unchanged). Never flip `stop_reason` / exit code from this signal
   alone. `self-seeded-finding` stays `judgment_only` in the
   audit-shapes registry.

5. **Order** — writer first (so history starts carrying notes), then
   diagnostic. Diagnostic against walk-only annotations is out of
   Outcome.

---

## Scope contract

### Outcome

See Outcome above.

### In scope

- Shared annotation/remedy-note writer used by interactive walk,
  `completeness-apply` (serial + parallel), and the new hand-apply
  record CLI.
- Thin completeness-family CLI to record `applied` / deliberate
  decline on a saved report (by id and/or anchor).
- Same-issue identity helper per settled tiers; wire into the
  bad-fix diagnostic (share helpers with `_matches` where safe;
  do not silently change existing `_matches` consumer semantics
  without tests).
- Recommend-only bad-fix advisory on `plan-tool convergence` (+
  optional completeness-iterate stderr when evidence already loaded).
- Synthetic history fixtures: fire only with identity + intervening
  note; no-fire for identity-only, note-only, mismatched identity,
  missing history.
- Docs: `DATA_CONTRACT.md` annotations producer list; DIRECTIVES /
  CLAUDE.md hand-apply recipe names the record command; backlog
  `#231` update in the final docs/status step.

### Out of scope / Non-goals

- Hard edit-drift / iterate stop, exit-code flip, `--fail-on-findings`
  change.
- Plan mutation, auto split / scope-out / re-seed (`#159` / `#160` /
  `#168` / `#116`).
- Raw full-body Claude issue similarity as primary matcher; prose
  “sounds like last edit” grading.
- Converting `self-seeded-finding` into a gate; second provenance
  store when `annotations` can carry the note.
- Changing stage bars (`#91` / `#248`); reporting polish `#260`;
  four-loop consistency `#261`; Stage 4 `#241` / `#164`; Stage 5 chat.
- Detail-prompt fence copy (`#229`).

### Allowed behavior changes

- New annotations from hand-apply record CLI and from any apply path
  that previously skipped writing them.
- New recommend-only advisory lines when the settled predicate fires;
  otherwise silent on this channel.

### Allowed reorganization

- Extract shared writer beside `update_annotation` if that keeps walk /
  apply / CLI thin; no drive-by folder moves.

### Verification

- Writer: walk, parallel apply, and record CLI each leave a durable
  `Annotation` on the sidecar; mutation removing the writer call goes
  red at each site.
- Identity: fixture pairs covering each tier win order; equal-id fast
  path; id-churn still matches via anchor or skeleton.
- Diagnostic: fire only when identity ∧ intervening note; each
  disqualifier silent; no import of retired fork/region APIs; no
  `stop_reason` / exit-code change.

### Stop / defer

- Valid out-of-scope findings → `BACKLOG.md` / `BUG_BACKLOG.md`.
- Hard exit keyed on this signal → future entry after this ships.
- Re-seed actuation after a named seam → `#159` / `#160` / `#168`
  after their own re-premise.
