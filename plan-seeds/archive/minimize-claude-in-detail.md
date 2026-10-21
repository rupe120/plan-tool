# Plan seed: minimize Claude round-trips in `detail`

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/minimize-claude-in-detail.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Guiding principle

**Apply the create-side lesson to `detail`: pay Claude for judgment, not
for what a deterministic check can decide or fill.** In `create` the
waste was a deterministically-detected `_(TODO)_` placeholder being
*filled* by a per-section Claude `apply_finding` call (see
[`minimize-claude-in-create.md`](minimize-claude-in-create.md)). `detail`
authors a richer seven-section body per step under `--iterate`, so the
same pattern likely recurs at larger scale. This work is **audit-first,
then apply**: map every Claude round-trip in `detail`, classify each as
judgment-required vs deterministically-resolvable, and convert the
resolvable ones.

## Phase A — audit (deliverable: a Claude-call inventory)

Enumerate every invoker round-trip in the `detail` flow (`detail.py` +
what it calls), each with phase, function, and purpose. Known anchors to
start from:

- The seven-section authoring call(s) and the `detail-quality.md`
  iteration loop (the analogue of create's body synthesis + apply loop).
- The purity self-check (`_parse_purity_findings`, `detail.py:784`) — its
  *detection* is regex over a `## Structural findings` block, but the
  judgment is Claude-authored prose; note which half is deterministic.
- Phase B split proposals (`_propose_step_split`) — Claude per mixed step.
- Any per-iteration re-authoring that re-runs Claude even when the prior
  round changed nothing structural (mirror of create Opportunity 3).

For each round-trip, label: **judgment-required** (semantic authoring,
contract reasoning) vs **deterministically-resolvable** (placeholder
detection, section-presence checks, gate enumeration, file/path
existence, the seven-section *structural* gate).

## Phase B — convert the resolvable ones

For findings whose *detection* is already deterministic and whose *fix*
is derivable or a sentinel, resolve without `apply_finding`:

- **Seven-section / structural gate misses** that are presence/shape
  problems (a missing required section, an empty placeholder) should be
  filled or flagged deterministically before spending a Claude apply,
  exactly as create's body-completeness placeholders will be.
- **Per-step Testing / boilerplate** content that mirrors a deterministic
  block (as in create's per-step Testing enumeration) should be templated,
  not Claude-authored.
- **Redundant per-iteration re-authoring:** gate re-authoring on whether
  the round applied a finding that could change the section it would
  re-author; skip when it provably couldn't. Conservative default:
  re-author when unsure.

Keep genuinely semantic work (Implementation prose, grounding/citation
reasoning, cross-step contract checks, the MIXED-STEP purity judgment) on
Claude.

## Phase C — surface deterministic resolution distinctly — CONDITIONAL (likely moot)

> **Carry-over caveat from the create pass:** this mirrors create's Opp 2b,
> which was **discarded** — it presupposes deterministic *fills*, and the
> create evidence showed those mostly regress quality (substantive
> sections, not boilerplate). Only pursue this for `detail` if Phase B
> actually finds a deterministic-fill path worth shipping. If `detail` has
> no deterministic resolution, there is nothing to label distinctly and
> this phase is dropped — do not add a `mechanism` field speculatively
> (create added one and removed it).

*If* `detail` ships a deterministic resolution, it must be **reported**
differently from a Claude `apply-finding` (which shares the
`launcher.py:2393` `apply-finding step {id}: …` badge): give it its own
progress label / phase so a free fill is never mistaken for a Claude edit.

## Do not regress

- **Author quality unchanged.** The seven-section contract
  (`DETAIL_FORMAT.md`) and grounding/citation gates stay intact; this
  only changes *who* fills deterministic gaps.
- **Sentinels are not placeholders.** Any deterministic fill must not trip
  the placeholder regex or the seven-section gate.
- **Don't fork purity.** If touching `_parse_purity_findings`, align with
  the granularity advisor seed
  ([`step-granularity-advisor.md`](step-granularity-advisor.md)) rather
  than duplicating logic.
- **Exit-code convention / concise docs / acyclic layering** per repo
  norms; update `TESTING.md`'s neutralization table if a seam changes.

## Out of scope

- The `create` process — its own seed.
- Removing `--iterate` or changing the convergence contract.
- The split/merge executors and the advisor (their own seeds) — except to
  avoid duplicating purity logic.
