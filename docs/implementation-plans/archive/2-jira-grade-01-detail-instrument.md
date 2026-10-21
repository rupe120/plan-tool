> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Jira Grade 01 Detail Instrument
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract detail artifact path resolution into a shared plan_tool/detail_artifacts.py
    leaf (behavior-preserving, characterization tests pinned first)
  files:
  - plan_tool/detail.py
  - plan_tool/fingerprint.py
  - plan_tool/review.py
  - plan_tool/scope_out.py
  - plan_tool/__init__.py
  creates:
  - plan_tool/detail_artifacts.py
  - tests/test_detail_artifacts.py
  complexity: medium
  change_type: refactor
  gate:
  - uv run pytest tests/test_detail_artifacts.py -q
  - uv run python -c "import sys, types; pkg=types.ModuleType('plan_tool'); pkg.__path__=['plan_tool'];
    sys.modules['plan_tool']=pkg; import plan_tool.detail_artifacts; bad=[m for m
    in sys.modules if m in ('plan_tool.review','plan_tool.detail') or m.startswith('plan_tool.cli')];
    sys.exit('detail_artifacts leaf pulled '+', '.join(bad) if bad else 0)"
  - '! grep -rnE "from (plan_tool\.|\.)detail import[^#]*(derive_detail_path|derive_step_slug|_plan_slug|find_unreferenced_detail_for_step)"
    plan_tool/fingerprint.py plan_tool/review.py'
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/01-extract-detail-artifact-path-resolution.md
  status: done
- id: 2
  title: Make a step with an unset Step.detail pointer but an on-disk canonical detail
    file visible to the completeness quality audit
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  allowed_mentions:
  - plan_tool/cli/completeness_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/02-make-step-unset-step-detail-pointer-but.md
  status: done
- id: 3
  title: 'Add the jira-grade schema authority module: required-H2 tokens (Intent,
    Change, Constraints, Done when, Out of scope), read-time validator, plain-English
    gate, and collision-safe jira-grade artifact paths'
  files:
  - plan_tool/detail_artifacts.py
  creates:
  - plan_tool/jira_grade.py
  - tests/test_jira_grade.py
  complexity: medium
  change_type: feature
  gate:
  - uv run pytest tests/test_jira_grade.py -q
  - uv run python -c "import sys, types; pkg=types.ModuleType('plan_tool'); pkg.__path__=['plan_tool'];
    sys.modules['plan_tool']=pkg; import plan_tool.jira_grade; bad=[m for m in sys.modules
    if m in ('plan_tool.detail','plan_tool.review','plan_tool.jira','plan_tool.launcher')
    or m.startswith('plan_tool.cli')]; sys.exit('jira_grade pulled '+', '.join(bad)
    if bad else 0)"
  - '! grep -rn ''\.jira\.md'' plan_tool/'
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/03-jira-grade-schema-authority-module.md
  status: done
- id: 4
  title: Add a jira-grade authoring mode to plan-tool detail with its own prompt and
    response gate, bypassing the run-grade quality loop and leaving Step.detail run-grade-only
  files:
  - plan_tool/detail.py
  - plan_tool/cli/authoring.py
  - docs/cli/detail.md
  - tests/test_detail.py
  - tests/cli/test_authoring_cmds.py
  creates:
  - plan_tool/prompts/detail-jira.md
  allowed_mentions:
  - plan_tool/prompts/detail.md
  - plan_tool/prompts/run-jira.md
  complexity: high
  change_type: feature
  gate:
  - uv run python -c "from pathlib import Path; body=Path('plan_tool/prompts/detail-jira.md').read_text();
    missing=[t for t in ('Intent','Change','Constraints','Done when','Out of scope')
    if t not in body]; raise SystemExit('prompt missing H2s '+', '.join(missing) if
    missing else 0)"
  - uv run plan-tool detail --help | grep -q -- '--grade'
  depends_on:
  - 1
  - 3
  - 5
  - 6
  - 9
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/04-jira-grade-authoring-mode-plan-tool.md
  status: done
- id: 5
  title: 'Let plan-tool jira consume jira-grade detail directly: grade option, selected
    path map threaded through export, and hard failure with contract re-validation
    when the jira-grade artifact is missing or mislabeled'
  files:
  - plan_tool/jira.py
  - plan_tool/cli/jira_cmd.py
  - docs/cli/jira.md
  - tests/test_jira.py
  - tests/cli/test_jira_cmds.py
  allowed_mentions:
  - plan_tool/cli/direct_cmd.py
  - plan_tool/jira_grade.py
  complexity: medium
  change_type: feature
  gate:
  - uv run plan-tool jira --help | grep -q -- '--grade'
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/05-let-plan-tool-jira-consume-jira-grade.md
  status: done
- id: 6
  title: 'Add the opt-in jira-grade run renderer: a detail-grade option that keeps
    public --mode run, a run-jira prompt, grade-aware detail loading with no silent
    fallback, threaded through run_step, sweep, resume commands, and run-log flags'
  files:
  - plan_tool/renderer.py
  - plan_tool/launcher.py
  - plan_tool/cli/run_cmd.py
  - docs/cli/run.md
  - tests/test_renderer.py
  - tests/test_launcher.py
  - tests/cli/test_run_cmd.py
  creates:
  - plan_tool/prompts/run-jira.md
  allowed_mentions:
  - plan_tool/prompts/run.md
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool run --help | grep -q -- '--detail-grade' && ! uv run plan-tool
    run --help | grep -q 'run-jira'
  - test -f plan_tool/prompts/run-jira.md
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/06-opt-jira-grade-run-renderer-detail.md
  status: done
- id: 7
  title: 'Ground the completeness audit on the selected grade''s bundle: resolution,
    prompt framing, and the fingerprint grade axis'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - plan_tool/fingerprint.py
  - docs/cli/completeness-audit.md
  - tests/cli/test_completeness_cmd.py
  - tests/test_review.py
  - tests/test_fingerprint.py
  complexity: medium
  change_type: feature
  gate:
  - uv run plan-tool completeness-audit --help | grep -q -- '--grade'
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/07-ground-completeness-audit-on-selected.md
  status: done
- id: 8
  title: 'Make the completeness audit''s deterministic detectors individually dispatchable:
    split the smell and self-consistency fan-outs behind a registry (behavior-preserving,
    characterization tests pinned first)'
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: refactor
  gate:
  - uv run pytest tests/cli/test_completeness_cmd.py -q -k "registry or characterization"
  depends_on:
  - 7
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/08-make-completeness-audit-deterministic.md
  status: done
- id: 9
  title: Classify every deterministic check on the grade axis and make the jira-grade
    report surfaces grade-correct, closed by a registration test
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - plan_tool/review.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  - tests/test_review.py
  allowed_mentions:
  - plan_tool/jira_grade.py
  - plan_tool/bench.py
  - plan_tool/cli/inspect.py
  - plan_tool/prompts/plan-audit.md
  - DETAIL_FORMAT.md
  - DATA_CONTRACT.md
  - docs/AUDIT_FLOW.md
  complexity: medium
  change_type: feature
  gate:
  - uv run pytest tests/cli/test_completeness_cmd.py -q -k grade
  depends_on:
  - 8
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/09-classify-every-deterministic-check-on.md
  status: done
- id: 10
  title: 'Update docs and close out the backlog: jira-grade contract in DETAIL_FORMAT.md/JIRA_FORMAT.md
    and the flow docs, mark BACKLOG #164 instrument-shipped/evaluation-pending, and
    re-scope #149 to alias the jira-grade tokens'
  files:
  - DETAIL_FORMAT.md
  - JIRA_FORMAT.md
  - DATA_CONTRACT.md
  - docs/DETAIL_FLOW.md
  - docs/RUN_FLOW.md
  - docs/AUDIT_FLOW.md
  - CAPABILITIES.md
  - USE_CASES.md
  - BACKLOG.md
  - CLAUDE.md
  allowed_mentions:
  - ../DETAIL_FORMAT.md
  complexity: low
  change_type: non-code
  gate:
  - grep -q -- '--grade' docs/DETAIL_FLOW.md && grep -q -- '--detail-grade' docs/RUN_FLOW.md
    && grep -q -- '--grade' docs/AUDIT_FLOW.md
  - grep -q 'Done when' DETAIL_FORMAT.md && grep -q 'Out of scope' DETAIL_FORMAT.md
    && grep -q 'instrument-shipped' BACKLOG.md && ! grep -q 're-scopes this entry'
    BACKLOG.md
  depends_on:
  - 4
  - 5
  - 6
  - 9
  detail: docs/implementation-plans/plan-details/jira-grade-01-detail-instrument/10-update-docs-close-out-backlog-jira.md
  status: done
---
# Jira Grade 01 Detail Instrument

## Intent

Make both detail grades authorable, selectable, consumable, and auditable for one plan, so the jira-grade altitude becomes a real option rather than a proposal. This stage builds the instrument and measures nothing: run-grade stays the default and canonical grade everywhere, legacy bundles are untouched, and no adoption decision is taken here. Its success condition is that a later stage *can* ask the quality question at all — which requires an authoring mode, two consumers, and an audit that grounds on whichever grade is selected.

## Overview

Add an explicit jira-grade detail authoring altitude beside the existing run-grade path so one plan can carry a bundle of each grade. The group's direction is already decided and is not re-opened here: the jira-grade artifact is the **communication** artifact — a compact statement of intent a stakeholder, an implementer, and a reader six months later can each hold in their head — and `run` is a consumer of that guidance (2026-07-22, settled; see Problem statement). Run-grade remains the default everywhere; legacy bundles are always read as run-grade and never rewritten or reinterpreted. `jira` consumes jira-grade detail directly; an opt-in `run` path renders from it while the run-grade renderer remains intact and unchanged as the default; and the completeness audit can ground on whichever grade is selected, making both bundles independently auditable. This plan is stage 01 of 05 in the ordered `jira-grade` group (arc: BACKLOG #169, re-decomposing BACKLOG #164) and ships no evaluation and no default change — it builds the instrument the later stages read. What those stages measure was re-decided on 2026-07-29: stage 05's canonical inversion is gated on **stage 02's probe actionability** (jira-grade bundles must produce no-worse anchored blocker findings), not on audit-finding churn, because probe blockers anchor to code while a finding-set delta is sampled prose. Stage 03 still measures churn if its noise floor permits, but nothing downstream waits on that number. This plan is unaffected either way: it ships the same instrument whichever measurements the later stages choose to run.

## Problem statement

The predecessor plan `2-jira-grade-detail-side-by-side-evaluation` fused two concerns that converge under different audit regimes — *building the instrument* (ordinary software, converges under tests and completeness audit) and *running a defensible experiment* (epistemics: isolation, metric definition, rubric, sample size) — and spun on its completeness convergence tail (verdict `FORK_STRUCTURAL`; latest report [retained historical summary](../../evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)). Three blockers recurred across all three audit snapshots without shrinking, and the seam between build and measure is where each partition's findings become locally closable. This plan takes the build side and directly resolves the blockers that live here:

- **`audit-churn` (CRITICAL, fence conflict):** the inherited fence forbade completeness-audit changes while the adoption gate required measuring churn on the jira-grade bundle — but the audit grounds on the run-grade `Step.detail` pointer, so both arms audited the control. Resolved by the narrow fence amendment (see Architecture's "Grade-aware audit grounding (the amended surface)" and the audit-judgment bullets under Out of scope).
- **`step-1-type-purity` (MEDIUM, fused concerns):** the old step 1 mixed a behavior-preserving extraction with new audit-inclusion behavior. Resolved by splitting them into separate refactor and feature steps.
- **`artifact-ambiguity` (HIGH):** consumers validated only path existence, so a run-grade body at the jira-grade path would be read under the jira-grade prompt. Resolved by contract validation on read.

**What motivates the group is communication value, and that direction is decided** (2026-07-22, user, settled; BACKLOG #169's "communication-first convergence arc"): the tool's primary value is the jira-grade communication artifact — a compact statement of intent a stakeholder, an implementer, and a reader six months later can each hold in their head — and `run` is a **consumer** of that guidance, not a co-equal metric. Nothing in this group is a contest between two grades to decide which is better; that was settled on communication grounds and must not be re-argued here.

A separate and **much weaker** claim has often been mistaken for the motivation: that jira-grade detail *churns less* than run-grade across a scope change, because its contradiction surface is smaller. It has only ever been inferred from post-mortems, never observed, and as of 2026-07-29 **nothing in the arc depends on it** — stage 05's inversion is gated on stage 02's probe actionability instead (see Overview). Stage 03 may still measure churn if its noise floor permits; treat it as a curiosity the group would like settled, not as the reason the group exists. Of the old measurement-side blockers, `paired-run-isolation` and `metric-noise` dissolved when the paired decision experiment was dropped (stage 03 is now a quality ledger — no paired runs, no single-pair gate); every surviving instrumentation concern — churn formula, actionability metric, provenance, floors, and the noise floor any comparison must clear — belongs to stage 03.

**This plan observes nothing.** It makes both grades authorable, selectable, consumable, and auditable — serving the decided communication direction, and leaving the later stages able to check that adopting it costs implementers nothing.

## Architecture

### Schema authority (one authority, never two)

The jira-grade contract is the smallest shared schema both consumers can use: `Intent`/problem, `Change`, `Constraints`, `Done when`, `Out of scope` — outcomes and boundaries, not pre-baked edits, test rosters, or mechanics unless a declared constraint requires one.

**Authority decision (taken 2026-07-22, user-confirmed — carry it verbatim): this plan's schema step is the single compact-schema authority.** BACKLOG **#149**'s compact required-H2 schema (plan-authored: `detail-verbosity-compact-summary`, unexecuted) is **not** the base: #149's contract (`Intent`, `Footprint`, capped `Approach`, `Done when`) is a compact *run-grade* schema — its `Footprint`/`Approach` sections retain the implementation-fact carriers the jira-grade altitude sheds, it lacks `Constraints` and `Out of scope`, and the surface it compacts is scheduled to become derived at stage 05. The real overlap is `Intent` and `Done when` only. Therefore: this plan defines the jira-grade tokens as the durable authority, and the final docs/status step **re-scopes #149** so its authoring-schema layer aliases the jira-grade tokens (its read-only `--summary` review-card layer is unaffected and remains valuable). Audits must not re-open the sequencing question; "aligned with or sequenced after" hedging is not permitted to survive into the plan.

**Plain, concise English prose by contract.** Every prose surface this plan ships is written in plain, to-the-point English from day one: the jira-grade authoring prompt, the jira-grade run prompt (step 6's `plan_tool/prompts/run-jira.md` — a prompt template in the same class as the authoring one), the jira-grade bodies they ground, and the `jira` story output built from them use short, direct sentences and familiar words, say each thing once, and carry no filler — while keeping every technical fact (paths, symbol anchors, examples, constraints, acceptance criteria) intact. Both directives target the descriptive prose only: they never reduce code anchors or examples. This applies BACKLOG **#167**'s rubric (including its conciseness directive) to the new contract at birth rather than as a retrofit — #167 remains the authority for the existing run-grade `detail` output; this plan does not modify the run-grade prompts, it only refuses to create a second dense-prose surface. For the two model-produced surfaces the requirement is testable at the gate level: in the same pass that validates the required H2s, the jira-grade response gates block filler-phrase padding and over-long sentences (a hard sentence-word cap); clause-stacking heuristics stay advisory and jargon detection is not attempted, per #167's keep-heuristics-advisory rule (step 3 records this resolution). The two prompt templates are hand-authored files, not model output, so no runtime gate can enforce them — each carries the contract as an authoring constraint checked by its own step's acceptance criteria (step 4 for `detail-jira.md`, step 6 for `run-jira.md`).

### Storage, selection, and read-time validation

Add explicit grade selection and collision-safe artifact routing so run-grade and jira-grade bundles coexist for one plan (separate files under the plan's detail directory; never overloading `Step.detail`'s meaning for legacy bundles). Selection is explicit at every consumer, so there is no ambiguous-selection case to resolve — the grade is always named by a flag with a run-grade default, and the artifact path is derived, not searched. That leaves exactly **two** failure modes, and both fail clearly: a **missing** artifact under explicit jira selection, and a **mislabeled** one (a body that fails the required-H2 contract, e.g. run-grade prose at a jira-grade path).

**Bundle-coverage rule (one rule, three consumers).** A jira-grade bundle is **complete when every non-`done` step carries a conforming artifact** — `done` steps are exempt everywhere, mirroring `check_detail_coverage`'s deliberate skip and this plan's "done steps stay skipped at every site" pin (an implemented step's detail intent has served its purpose). A consumer may narrow further to the steps it actually consumes — `run` preflights only the in-scope steps it is about to execute — and no consumer may demand **more** than this rule *as a completeness verdict*, so the audit and the `jira` export cannot disagree about whether the same bundle is complete. One narrow execution-time exception, owned by step 6: an **explicitly requested** `done` step is exempt from the coverage rule but still cannot be executed with no body, so `run` fails on it as a *missing-artifact* error, never as a coverage verdict — the distinction the error text must carry. Where a `done` step has no artifact, it is simply absent from the selected map and renders with no detail body; it never falls back to the run-grade body, which would reintroduce the masked-contract failure. **Validation happens on read, not just on path existence:** consuming a jira-grade artifact re-validates its required-H2 contract first, so a run-grade body at a jira-grade path is rejected loudly rather than silently executed under the wrong prompt.

**The validator lands before the producer.** Step 4 (jira-grade authoring) depends on step 9 (the grade-aware deterministic battery and report surfaces, which completes the grade-aware audit begun in step 7), so the completeness audit understands the grade axis before any jira-grade artifact can exist. Without that edge the plan permits a partial state where `--grade jira` authors bundles no audit can resolve: contract-valid under the read-time validator above, but with no coverage or coherence check available at all. That state is not hypothetical — step 7 is gated behind step 2 while steps 4–6 need only steps 1 and 3, so following the unblocked work would produce artifacts ahead of the instrument that judges them. Gating step 4 fences the whole chain: with no authoring mode there are no bundles for the `jira` export or the `run` renderer to consume, and both fail loudly on a missing or mislabeled artifact rather than falling back, so neither needs its own edge. The dependency points backward in step numbering; that is deliberate and legal — `depends_on` carries no ordering constraint and the next runnable step is chosen by dependency satisfaction, not by id — so `plan-tool status` lists step 4 above steps 7–9 while execution runs both of those first.

### Refactor/feature separation

The shared detail artifact-path layer (e.g. `plan_tool/detail_artifacts.py`) is extracted as a pure behavior-preserving refactor with characterization tests pinned before the change, kept separate from the small audit-inclusion feature the old step 1 fused in — an unset `Step.detail` pointer with an on-disk canonical detail file becomes visible to quality auditing — whose own tests establish the new behavior independently of the refactor's compatibility.

### Consumers

`jira` consumes the jira-grade schema directly (no down-conversion from run-grade prose when a jira-grade bundle is selected). An opt-in jira-grade `run` renderer receives the same schema plus normal plan/repository grounding and asks the executor to derive the implementation; its output is separately selectable from the unchanged run-grade renderer, and no hidden fallback may mask which contract a run actually executed.

### Grade-aware audit grounding (the amended surface)

The completeness audit resolves the detail bundle for a requested grade and applies that grade's format contract to it — run-grade bundles keep today's behavior byte-for-byte when no grade is selected. The CLI spells the grade axis `--grade {run,jira}` on `detail`, `jira`, and `completeness-audit`; on `run` alone it is `--detail-grade {run,jira}`, because there the grade must not collide with the existing `--mode` lifecycle axis — one axis, two spellings, and `run`'s is the deliberate one (step 6 records why). The amendment covers resolution and format-contract selection — including the conceptual audit prompt's bundle framing, since pointing run-grade framing at a compact bundle applies the wrong contract as surely as reading the wrong file — plus the report-surface consequences the grade lane's own suppressions create: the operator-guidance prose must not name verbs the grade cannot serve, and one stderr notice announces what the run did not persist. Audit judgment — finding sources, severities, sampling, and convergence predicates — is untouched. The jira-grade lane is deliberately audit-and-report-only: it rejects `--iterate` and audit reuse and writes no findings sidecar, so run-grade reuse and convergence history can never be contaminated cross-grade — a narrowing of surface for safety, not a judgment change; its one new deterministic check is the jira bundle's coverage/contract validation (step 9 records this decision).

## References

- [Claude Code — Headless / programmatic mode](https://code.claude.com/docs/en/headless) — Official reference for running the `claude` CLI non-interactively (`-p`, allowed tools, output/stream formats), which governs how plan-tool's invoker seam shells out for jira-grade detail authoring and audits.
- [Jira Cloud platform REST API v3 — Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/) — Primary API reference for creating and updating issues (story fields, payload shape, permissions), relevant to what the `jira` export's story schema must ultimately map onto.
- [Atlassian Document Format — Structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/) — Defines the JSON node structure Jira Cloud requires for rich-text issue descriptions; relevant only if story bodies are ever created directly via the API, which this plan defers (the export stays markdown/JSON paste-ready — step 5's Deferred).
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Standard-library reference for subparsers, flags, and mutually-exclusive options, used when wiring the explicit grade-selection flags into plan-tool's per-intent CLI modules.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Official guide to `monkeypatch` for stubbing the Claude invoker seam and environment in the plan's characterization and gate tests.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — The formal Markdown spec for heading syntax, the ground truth for the required-H2 contract validation that read-time jira-grade artifact checks and response gates enforce.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Measuring the mechanism claim at all.** This plan builds the instrument and ships no evidence about churn. The one-off falsification check it used to carry was cut on 2026-07-29 and the question moved to `plan-seeds/jira-grade-03-quality-ledger.md`, which owns the churn formula, floors, and provenance — see that seed's "The mechanism question (moved from stage 01)" for why a single pair could not produce a reading. No step here may re-introduce a comparison, a control arm, or a churn claim.
- Restyling existing run-grade prompts or bundles into plain English — that is BACKLOG #167's scope; this plan only guarantees the new jira-grade surfaces are plain-English from birth.
- The consumer probe and `probe` verdict arm (stage 02, #169), blocker-recurrence materiality (stage 04, #170), and canonical inversion (stage 05, #171).
- Making jira-grade the default for `detail`, `run`, or `jira`; default inversion requires a later evidence-backed plan.
- Re-authoring or bulk-rewriting existing run-grade bundles.
- Changing plan-body schema, step decomposition, `change_type`, or any audit **judgment** surface (severities, sources, sampling, convergence predicates) — only the grounding amendment is open.
- Weakening audit checks in any form.

## Risks

- **Run quality regression:** deferred entirely — no run behavior changes by default. Whether executing from a jira-grade bundle costs implementers anything is checked later, by stage 02's consumer probe (the arc's evidence gate) and stage 03's `run` smoke-check records — not here, and not by a controlled comparison.
- **Artifact ambiguity:** explicit grade selection (which removes the ambiguous case by construction) + read-time contract validation + tests that reject the two real failure modes, missing and mislabeled.
- **Schema duplication with #149:** the one-authority rule (this plan's schema step is the single compact-schema authority); the plan must record which branch applied.
- **Fence creep:** the amendment is grounding-only. In scope: bundle resolution, format-contract selection (including the audit prompt's bundle framing), and the grade lane's own report-surface consequences — the grade-correct operator-guidance prose, the sidecar/convergence suppressions, and the stderr notice that announces them. Out of scope and routed to the backlog: any change to audit **judgment** — finding sources, severities, sampling, blocking gates, or convergence predicates.

## Testing

Cross-cutting coverage the seed requires (unit-first per the project convention; the per-step test-strategy enumeration owns per-step test ordering):

- Tests cover both contracts, legacy compatibility, selection, read-time validation, prompt routing, grade-aware audit grounding, and that no default changed.
- Tests reject both failure modes — a missing artifact under explicit jira selection and a mislabeled one; consuming a jira-grade artifact re-validates its required-H2 contract on read, so a run-grade body at a jira-grade path is rejected loudly rather than silently executed under the wrong prompt.
- Legacy bundles read and execute unchanged; no-grade-selected audit behavior is byte-for-byte except the deliberate canonical-only-visibility changes (step 2's audit inclusion — shared into the reconcile/review lanes by design — and its step-9-landed `completeness-apply` allowed-mentions handoff), each with its own tests.
- The plain-English requirement is enforced at the gate level: the jira-grade response gates block filler-phrase padding and over-long sentences in the same pass that validates the required H2s (clause-stacking heuristics advisory, no jargon detection — the decided step 3 design).
- The pure refactor is pinned by characterization tests before the change and passing unchanged after; the audit-inclusion feature's own tests establish the new behavior independently of the refactor's compatibility.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 9 (feature) — unit tests added with the implementation; green before completion.
- step 10 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Run-grade remains the default; legacy bundles read and execute unchanged. Audit behavior when no grade is selected is byte-for-byte today's, with two deliberate exceptions this plan ships: step 2's audit-inclusion feature makes a canonical-only detail file (unset `Step.detail` pointer, on-disk canonical file) visible to the quality audit — and, because the changed checks are shared, to the reconcile/review lanes (`collect_deterministic_findings`, `review_plan_full`), which is intended — and step 9 lands step 2's handoff, threading `plan_path` into `completeness-apply`'s allowed-mentions promotion, so canonical-only citations become visible there too. (Step 9 owns `plan_tool/cli/completeness_cmd.py`; the 7/8/9 carve moved this handoff there.)
- An explicit jira-grade mode produces, stores, and selects artifacts independently from run-grade for the same plan; consuming an artifact re-validates its contract, and both failure modes — mislabeled, and missing-under-explicit-selection — fail clearly — the consumers (`jira`, `run`) hard-fail before any backend call, while the audit surfaces both the mislabeled and the missing arm as blocking findings under the exit-code convention (rc flipped by `--fail-on-findings`) — carried on finding shapes the existing blocking gate already recognises, so no judgment surface is edited to make them block.
- Exactly one compact-schema authority exists, with the #149 branch recorded.
- One bundle-coverage rule governs all three consumers: a jira-grade bundle is complete when every non-`done` step carries a conforming artifact; a consumer may check a narrower set (`run`'s in-scope steps) but never a wider one, so the audit and the `jira` export never disagree on the same bundle.
- `jira` consumes jira-grade detail directly; an opt-in `run` path renders from it; the run-grade renderer is intact and behaviorally unchanged as the default; no hidden fallback masks the executed contract.
- One authored bundle flows end to end through every consumer before the plan closes — step 4's acceptance criteria carry a smoke check that authors a real jira-grade bundle and then exports it (`jira --grade jira`), renders a run prompt from it (`run --detail-grade jira --dry-run`), and audits it (`completeness-audit --grade jira`). It checks only that the pieces meet: nothing is counted and no run-grade counterpart is authored or compared (see Out of scope).
- The completeness audit grounds on the selected grade's bundle with that grade's format contract; audit judgment surfaces are demonstrably unchanged.
- Every deterministic check the audit runs is classified on the grade axis by a registry the dispatch reads, and the closure is held by **three** guards that can actually fail, each with a negative case. Two prove *registry* closure and belong to step 8: a source-level guard rejecting direct detector calls that bypass the registry, and characterization parity against the pre-refactor battery. Neither one tests that an entry carries a grade class, so neither proves the *classification* half of this criterion — that is step 9's "every registry entry has a grade class" test, and it is named here because a criterion whose own claim rests on an unnamed guard is a criterion nobody checks. A "reachable but unclassified" test is deliberately *not* the mechanism: once unregistered checks are unreachable it is true by construction and would have passed in every audit round of this plan (step 8 records the rejection).
- Every prose surface this plan ships is plain, concise English by contract: short, direct, to-the-point sentences with all technical facts, code anchors, and examples intact. Jira-grade bodies are enforced by the blocking authoring gates in the same pass that validates the required H2s; story output carries the plain-English directive in the export prompt — read-time validation stays structural (per #167's rubric, applied at birth; conciseness directed at descriptions only). Hand-authored prose carries no runtime gate and is checked by reading, under its own step's acceptance criteria: the two prompt templates `plan_tool/prompts/detail-jira.md` (step 4) and `plan_tool/prompts/run-jira.md` (step 6), plus step 5's plain-English directive block on the export prompt, step 7's jira framing substitution in `plan_tool/prompts/plan-audit.md`, and step 9's operator-guidance prose and stderr notice. The list is these five surfaces; a step that ships another adds it to its own acceptance criteria.
- Tests cover both contracts, legacy compatibility, selection, read-time validation, prompt routing, grade-aware audit grounding, and that no default changed.
- `BACKLOG.md` #164 Status reflects instrument-shipped / evaluation-pending; out-of-scope findings route to `BACKLOG.md` / `BUG_BACKLOG.md`.

## Deferred

- The quality ledger (stage 03) and any default inversion (stage 05).
- A prescriptive-supplement escape hatch for individual jira-grade steps; derive it from real blockers the consumer probe records, not from preemptive schema growth.
- Corpus migration or re-authoring policy — including the jira-artifact renumber-staleness lifecycle gap (unpointed `jira/` artifacts go stale across any step renumber: split, merge, or scope-out; consumers fail loudly in the meantime, and step 10 files the durable `BACKLOG.md` entry).
