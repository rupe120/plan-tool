# t2_residue — blind labeling

**Question.** Did the prior edit introduce the problem this finding describes? `yes` = the problem exists only because of text the edit added or changed; `no` = the problem was already present before the edit, or the edit is unrelated.

## 1. `roadmap-model-failure-receipts|2026-09-21T15:17:13Z|plan-plan-correctness-fd46f8a8`

**Cited step:** 1: Move detail raw-response sidecar writes to a shared owner while preserving best-effort whole-file replacement

**Finding (plan-correctness, medium):** The Overview falsely says “sidecar capture is currently a detail-specific convention,” but `plan_tool/create.py:_dump_fa

The Overview falsely says “sidecar capture is currently a detail-specific convention,” but `plan_tool/create.py:_dump_failed_response` also persists rejected create responses under `.plan-tool/parse-failures/` and explicitly says it mirrors `plan_tool.detail._log_parse_failure`. This can lead step 1 to document the shared owner as replacing the only existing convention while leaving the separate create owner correctly out of scope but inaccurately described.

**Suggested action:** Correct the Overview and step 1’s baseline description to distinguish the detail helper being consolidated from the separate, later-migration create sidecar writer.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-model-failure-receipts.md b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
index e96b2725..520c8bf4 100644
--- a/docs/implementation-plans/2-roadmap-model-failure-receipts.md
+++ b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
@@ -81,8 +81,8 @@ steps:
       gate diagnostics, and sidecar write failures.
 - id: 5
-  title: Record local feedback revision failures while preserving recoverable publication
-    replacement
+  title: Record local feedback revision failures and reply-bearing gate rejections while
+    preserving recoverable publication replacement
   intent: Give local --revise-feedback failures the same diagnostic evidence as roadmap
-    stage failures without duplicating gate-rejected artifacts.
+    stage failures, retaining a rejected reply only when no structured gate diagnostic exists.
   files:
   - plan_tool/roadmap_revision_run.py
@@ -94,6 +94,6 @@ steps:
   - 2
   depends_on_notes:
-    1: Provides best-effort raw-response persistence for reply-bearing failures before
-      gates.
+    1: Provides best-effort raw-response persistence for reply-bearing failures, including
+      a local gate rejection that has no structured diagnostic event.
     2: Provides the shared receipt emitted after the sidecar disposition is resolved.
 - id: 6
@@ -157,10 +157,12 @@ The sidecar disposition is a closed four-value contract:
 | `written` | The shared sidecar owner receives raw response bytes and writes them before receipt emission. | The receipt carries the safe path, byte count, and digest; the operator reads the sidecar. |
 | `no-response` | No response bytes exist; this takes precedence over every write state. | The receipt carries zero bytes and no path; the operator uses invocation metadata. |
-| `not-retained` | The failure has an owning structured diagnostic, currently a gate rejection, so policy does not request a raw sidecar. | The receipt points the operator to the structured diagnostic and carries no sidecar path. |
+| `not-retained` | The failure has an owning structured diagnostic, currently a fresh or bounded stage gate rejection, so policy does not request a raw sidecar. | The receipt points the operator to the structured diagnostic and carries no sidecar path. |
 | `write-failed` | Raw bytes exist and policy requests retention, but the best-effort write fails. | The receipt keeps byte count and digest without a path; the original retry or terminal outcome proceeds unchanged. |
 
 `invoke`, `parse`, and `authored-review-rows` are sidecar-eligible whenever raw
-bytes exist. Gate rejection remains `not-retained` because `gate_violations`
-and the parsed candidate supply its diagnosis. Successful responses emit no
+bytes exist. Fresh and bounded stage gate rejection remains `not-retained`
+because `gate_violations` supplies its diagnosis. A reply-bearing local revision
+gate rejection is sidecar-eligible because its terminal event has only the
+closed verdict, not a structured diagnostic. Successful responses emit no
 terminal-failure receipt.
 
@@ -199,5 +201,7 @@ See the `steps:` block in the frontmatter.
 
 - The later cross-command producer migrations named by the source BUG entry.
-- Persisting gate-rejected or successful raw responses.
+- Persisting fresh or bounded stage gate-rejected responses, or any successful
+  raw response. A reply-bearing local revision gate rejection is in scope because
+  it has no structured gate diagnostic.
 - Changing retry budgets, correction prompts, result outcomes, stdout, or exit
   codes.
@@ -224,8 +228,9 @@ Use a producer/rejection matrix over fresh authoring, bounded feedback, and
 local revision. Prove that every reply-bearing pre-gate rejection emits one
 redacted receipt per attempt, including a failed attempt followed by success;
-that `authored-review-rows` follows the settled sidecar policy; that gate
-rejections use structured diagnostics without a raw sidecar; and that success
-emits no failure receipt. Prove all four sidecar dispositions and show that a
-write failure leaves retries, results, stdout, and exit codes unchanged.
+  that `authored-review-rows` follows the settled sidecar policy; that fresh and
+  bounded stage gate rejections use structured diagnostics without a raw sidecar;
+  that a reply-bearing local revision gate rejection is retained; and that success
+  emits no failure receipt. Prove all four sidecar dispositions and show that a
+  write failure leaves retries, results, stdout, and exit codes unchanged.
 
 At the bare-plan gate, retain the shared receipt property, complete producer
@@ -241,6 +246,7 @@ producer/disposition pairing and the no-raw-JSONL invariant.
   succeeds.
 - Reply-bearing `invoke`, `parse`, `authored-review-rows`, and local revision
-  rejection outcomes follow the explicit sidecar policy; gates retain their
-  structured evidence without raw-response duplication.
+  rejection outcomes follow the explicit sidecar policy; fresh and bounded stage
+  gates retain structured evidence without raw-response duplication, while a local
+  gate-rejected reply remains diagnosable through its receipt and sidecar.
 - Receipt emission follows sidecar disposition resolution, and sidecar failure
   cannot change the real command outcome.

````

## 2. `arm-clustering-cross-round-consensus|2026-08-12T19:37:39Z|plan-plan-completeness-796d81f2`

**Cited step:** None: None

**Finding (plan-completeness, medium):** The Risks section covers misattribution only when `_matches` is bypassed ("if `_matches` is bypassed instead of reused")

The Risks section covers misattribution only when `_matches` is bypassed ("if `_matches` is bypassed instead of reused"); it never covers the same failure when `_matches` is used exactly as specified. `_matches`'s tier 1 ("step focus") matches two findings purely on a leading `step<N>`/`step-<N>` token parsed out of `anchor` (`c_focus == r_focus`), with no additional check that the anchors or titles agree. Plan-audit findings always carry `step_id=None`, so two genuinely different findings that both happen to be anchored `step5-...` in different rounds would match at tier 1, letting the newer one inherit an unrelated older finding's `audit_step_target` as if it were the same finding recurring — fabricating the two-round recurrence evidence this plan exists to require, for a finding that is really new this round.

**Suggested action:** add this as a named risk distinct from the bypass case already listed, and add a testing case with two differently-worded findings sharing a leading step token across two rounds, asserting they are never treated as one recurring finding for consensus.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index dc35c926..d82b3756 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -80,6 +80,10 @@ steps:
   title: Update the docs for the cross-round advisory and settle the backlog entries
   intent: 'Keep the always-injected guidance honest once this ships, so the next session
-    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim,
-    or an open #264 as still true.'
+    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim
+    in CLAUDE.md, `convergence_diagnosis.py`''s own matching "cycle-free leaf" docstring
+    paragraph, or `docs/ARCHITECTURE.md`''s third restatement of the same
+    "review_persistence, review, locator, convergence" import list (all three name the
+    same fact and all three need the same audit_shapes.py import added by step 2), or
+    an open #264 as still true.'
   files:
   - CLAUDE.md
@@ -87,4 +91,5 @@ steps:
   - docs/AUDIT_FLOW.md
   - BACKLOG.md
+  - plan_tool/convergence_diagnosis.py
   complexity: medium
   change_type: non-code
@@ -144,10 +149,14 @@ settled precedent, not a gap to redesign.
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
-2. Materiality: treat a saved finding as material via
+2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   — the same rule `classify_edit_drift`'s `_edit_drift_eligible` already
-   applies to `RunFinding` objects pulled from history
-   (`convergence_diagnosis.py:885`). This is a different, deliberate choice
-   from same-execution arm-clustering's `is_blocking_impact` +
+   checked **only against the newest round's copy** of that finding — the
+   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
+   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
+   and the same newest-round keying point 7 already uses for the output
+   mapping. A finding's severity/impact tag can differ across matched rounds;
+   only the newest round's copy decides materiality, never a mix or an
+   older round's. This is a different, deliberate choice from same-execution
+   arm-clustering's `is_blocking_impact` +
    `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
    which rebuilds a live per-run calibration lookup and was designed for a
@@ -176,8 +185,17 @@ settled precedent, not a gap to redesign.
    targets disagree; a target is missing on some round; a step's renumbering
    breaks target continuity even though the finding still matches by
-   anchor/title; **or** the single agreed target is not among the *current*
-   round's `declared_step_ids` (the step was deferred, marked `wont_do`,
-   deleted, or renumbered since the last matched round). Never guess a target
-   and never pass an unresolved or stale one through.
+   anchor/title; the single agreed target is not among the *current* round's
+   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
+   renumbered since the last matched round); **or** the target step's current
+   `status` is `done`. `declared_step_ids` / `committed_step_ids` is built
+   from `StepScope.COMMITTED` (`completeness_report.py:122`,
+   `review.py:8059`), which is the commitment axis, not the lifecycle axis
+   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
+   stays in that list, so list membership alone cannot detect a target that
+   shipped between the matched rounds and a later `plan-tool convergence`
+   read. Check the target step's `status` directly; this plan's own
+   governing rule (a `done` step is "shipped: context, never a target") is
+   how a stale-but-shipped target must be treated here too. Never guess a
+   target and never pass an unresolved or stale one through.
    `evaluate_arm_clustering` returns `None` for the *entire* advisory the
    moment any id in `material_finding_ids` lacks a target inside the
@@ -188,5 +206,21 @@ settled precedent, not a gap to redesign.
    ids), that same resolved-subset `material_finding_ids`, and the newest
    round's committed `declared_step_ids` into `evaluate_arm_clustering`
-   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+   unchanged. Two more of the leaf's parameters are not optional in practice
+   and must be supplied, matching same-execution's own call
+   (`review.py:8064-8076`): `material_finding_evidence` — built from the
+   newest round's own `RunFinding.anchor`/`.source` for each resolved id
+   (already-persisted fields, no new plumbing) — since an empty evidence
+   tuple defaults every item to `anchor=None`, which
+   `completeness_report.py`'s renderer (`_advisory_arm_steps`,
+   line ~149-157) skips, leaving the printed arm's finding list empty; and
+   `source_plan_fingerprint` — the plan's *current* fingerprint computed at
+   call time (not a saved round's), matching how same-execution stamps
+   `audit_input_snapshot.fingerprint` and how `completeness_report.py`'s
+   `matches_disk` staleness check consumes it. Leaving either at its
+   signature default (`()` / `""`) is a caller bug, not a valid choice: an
+   empty `source_plan_fingerprint` fails `_is_valid_stored_arm_advisory`'s
+   own non-empty check (`audit_shapes.py:121`) and voids the advisory
+   outright. The leaf's own gap-free proper-majority-arm math is not
+   touched.
 8. When the classifier has nothing to report — including when a previously-
    firing arm's cross-round consensus becomes unresolvable — the render emits
@@ -253,5 +287,5 @@ See the `steps:` block in the frontmatter.
   the field and its `DATA_CONTRACT.md` entry must land in the same step, not
   split across steps 1 and 5.
-- A silent non-fire (Architecture point 7) is easy to misread from the outside
+- A silent non-fire (Architecture point 8) is easy to misread from the outside
   as "the arm resolved" rather than "evidence became unavailable." Acceptance
   criteria settle this as accepted, explicitly-decided behavior rather than a
@@ -260,4 +294,9 @@ See the `steps:` block in the frontmatter.
 - Windowing on the wrong `audit_stage` (mixing bare and detail history) would
   manufacture a consensus target that never coexisted in one coherent audit.
+- `evaluate_arm_clustering`'s `material_finding_evidence` and
+  `source_plan_fingerprint` both default to empty/falsy values that are easy
+  to leave unset by omission rather than by decision — the former silently
+  degrades the render, the latter silently voids the whole advisory. Both are
+  named explicitly in Architecture point 7 so they are supplied by decision.
 
 ## Testing
@@ -266,22 +305,31 @@ Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
 saved `Recommendation`/`RunFinding` via `save_review`/`resolve_saved_review`,
 documented in `DATA_CONTRACT.md`; (2) materiality for cross-round consensus is
-computed via `is_blocking_finding` (stage-aware, matching
-`classify_edit_drift`'s own use on `RunFinding`s), independent of and not
-required to agree with same-execution's `is_blocking_impact` +
-calibration-lookup materiality; (3) a finding with a stable `_matches` identity
-and one agreeing persisted `audit_step_target` across the 2-round window
-produces a resolved consensus target; (4) a finding whose matched target
-disagrees, is missing on one round, or agrees across the window but is absent
-from the *current* `declared_step_ids` (deferred/`wont_do`/deleted/renumbered
-since the match), is dropped from **both** `consensus_targets` and the
-`material_finding_ids` passed to `evaluate_arm_clustering`, never causing the
-whole advisory to return `None`; (5) a renumbered step that 
````

## 3. `roadmap-terminal-error-contract|2026-09-21T16:21:49Z|plan-plan-correctness-b7f4ed57`

**Cited step:** 3: Preserve preflight and mid-run writer-guard origins while keeping publication replacement and cleanup unchanged

**Finding (plan-correctness, high):** Step 3 (`Preserve preflight and mid-run writer-guard origins...`) distinguishes writer-guard origins, but steps 3 and 5 

Step 3 (`Preserve preflight and mid-run writer-guard origins...`) distinguishes writer-guard origins, but steps 3 and 5 never give a writer-guard refusal during guard acquisition a run-log route. At HEAD, `roadmap.py:run_roadmap` acquires and validates the writer before `_run_roadmap` opens `_roadmap_command_lifecycle`, and `cli/roadmap_cmd.py:_cmd_roadmap_materialize` does the same before `_cmd_roadmap_materialize_owned` opens its lifecycle. The acceptance criterion therefore cannot hold for those required preflight exits:

  ```
  Acceptance criteria: Every ordinary exception exit in the primary `run_roadmap` and materialization lifecycle emits exactly one roadmap-level terminal status fact and a run-log ending consistent with its human message, selected return code, and crash behavior.
  ```

**Suggested action:** Make the disposition matrix and steps 3 and 5 explicitly assign pre-lifecycle writer-guard refusals to a terminal-record boundary that produces their status fact, run-log ending, exit code, and crash behavior.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-terminal-error-contract.md b/docs/implementation-plans/2-roadmap-terminal-error-contract.md
index 33d13a5f..61c01a4b 100644
--- a/docs/implementation-plans/2-roadmap-terminal-error-contract.md
+++ b/docs/implementation-plans/2-roadmap-terminal-error-contract.md
@@ -73,11 +73,14 @@ steps:
       and exception families.
 - id: 5
-  title: Emit one roadmap terminal status for every ordinary exception exit
+  title: Apply each terminal disposition across the primary, materialization, and local
+    revision exits
   intent: Keep human output, status facts, run-log completion, exit codes, and crash
-    persistence consistent for every ordinary primary stage-run exit.
+    persistence consistent for every ordinary primary-stage and named template-route exit.
   files:
   - plan_tool/roadmap.py
+  - plan_tool/roadmap_revision_run.py
   - plan_tool/cli/roadmap_cmd.py
   - tests/test_roadmap.py
+  - tests/test_roadmap_revision_run.py
   - tests/cli/test_roadmap_cmd.py
   - tests/cli/test_app.py
@@ -92,5 +95,6 @@ steps:
     3: Supplies the origin distinction needed to choose usage versus runtime-failure
       handling.
-    4: Makes all four named template routes enter the expected roadmap exception family.
+    4: Makes all four named template routes enter the expected roadmap exception family
+      before this step applies their common terminal disposition.
 - id: 6
   title: Reconcile the shipped terminal-error backlog records
@@ -151,8 +155,12 @@ Exception origin is preserved before the common CLI catch erases it, using the
 smallest typed or wrapped distinction that makes the matrix enforceable.
 Template readers translate expected path/read/decode failures into the
-appropriate roadmap exception family at their owning seam. The roadmap CLI
-emits the terminal status selected by the matrix exactly once, after the last
-stage fact and before returning or re-raising. Status reporting remains
-best-effort and cannot replace the original exception.
+appropriate roadmap exception family at their owning seam. The disposition
+application owns the primary run lifecycle, its CLI exception result, the
+materialization lifecycle/CLI pair, and the local-revision run/CLI pair. It
+selects the same terminal status, run-log ending, exit code, and crash behavior
+for equivalent template failures, emits the status exactly once after the last
+stage fact, and preserves the primary lifecycle's selected exit code rather
+than a default error code. Status reporting remains best-effort and cannot
+replace the original exception.
 
 ## Scope guardrails
@@ -217,11 +225,13 @@ See the `steps:` block in the frontmatter.
 ## Testing
 
-Use a disposition matrix across the CLI exception branches and renderer entry
-routes. Prove the same expected template failure yields the same human error,
-terminal status, run-log ending, exit code, and no crash file whether reached
-through fresh stage authoring, bounded feedback, local revision, or seed
-materialization. Prove preflight and mid-run writer-guard failures select their
-different dispositions. Prove an unexpected exception still reaches the
-application crash path after exactly one roadmap terminal status fact.
+Use a disposition matrix across the primary run lifecycle/CLI pair, the
+materialization lifecycle/CLI pair, the local-revision run/CLI pair, and the
+renderer entry routes. Prove the same expected template failure yields the same
+human error, terminal status, run-log ending, exit code, and no crash file
+whether reached through fresh stage authoring, bounded feedback, local revision,
+or seed materialization. Prove the selected primary and materialization exit
+code matches the run-log ending, preflight and mid-run writer-guard failures
+select their different dispositions, and an unexpected exception still reaches
+the application crash path after exactly one roadmap terminal status fact.
 
 At the bare-plan gate, retain the disposition fields, origin boundary, and
@@ -235,11 +245,13 @@ each named producer route.
   producer, precedence, consumers, exit code, crash behavior, and operator path
   for every value.
-- Every ordinary exception exit in the primary `run_roadmap` dispatch emits
-  exactly one roadmap-level terminal status fact consistent with its human
-  message, run log, return code, and crash behavior.
+- Every ordinary exception exit in the primary `run_roadmap` and materialization
+  lifecycle emits exactly one roadmap-level terminal status fact and a run-log
+  ending consistent with its human message, selected return code, and crash
+  behavior.
 - Preflight and mid-run writer-guard failures remain distinguishable after they
   reach the CLI boundary.
 - Equivalent prompt-template read/decode failures across all four named routes
-  receive the same expected-failure treatment.
+  receive the same expected-failure terminal disposition, including status,
+  run-log ending, exit code, and crash behavior.
 - Unexpected exceptions are not laundered into expected roadmap errors, and a
   reporting failure cannot replace the original exception.

````

## 4. `arm-clustering-cross-round-consensus|2026-08-12T19:02:48Z|plan-plan-correctness-a8f76be2`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-correctness, high):** Step 1 (Build arm-clustering consensus targets from saved audit history) has to decide which saved findings count as "ma

Step 1 (Build arm-clustering consensus targets from saved audit history) has to decide which saved findings count as "material" before matching them across rounds, but the plan never names that rule — and the codebase already has three different, disagreeing ones for similar-sounding jobs. Same-execution arm-clustering marks a finding material with `is_blocking_impact(rec, demote_low_impact_medium=...)` (`review.py`, using a fresh per-run calibration lookup from `build_low_impact_demotion_lookup(repo_root)`); `classify_impact_recurrence` uses the raw persisted `impact == "high"` flag; `classify_edit_drift` uses `is_blocking_finding(..., stage=...)`. `is_blocking_impact` has never been called on a saved `RunFinding` before — only on a live `Recommendation` — so reusing it cross-round also means rebuilding the calibration lookup when reading saved history, which no step currently plans for. Testing item 2's claim that the cross-round result is "equivalent to today's same-execution result" only holds if the plan picks that same rule, so this is a real open choice, not free implementation room.

**Suggested action:** in step 1, name the exact rule "material" reuses for cross-round history (most likely `is_blocking_impact` re-applied to the persisted severity/impact fields plus a calibration lookup rebuilt from `repo_root` at read time), say where that `repo_root` comes from at read time, and carry the same named rule everywhere "material"/"material_finding_ids" appears — Architecture points 5–6 and Testing items 2, 3, 4, and 6 — not just where it's first introduced.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index db7fb541..b072fcd1 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -14,10 +14,17 @@ steps:
 - id: 1
   title: Build arm-clustering consensus targets from saved audit history
-  intent: Let a material finding earn a consensus step target from separate audit
-    rounds, so arm-clustering has evidence to work with on the --audit-passes 1 runs
-    that give it only one same-execution sample.
+  intent: Persist the plan-audit's existing `[audit-step:N]` per-finding target onto
+    `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
+    and then discarded into a transient in-call structure before a review is saved),
+    then let a material finding earn a consensus step target from that persisted
+    value across separate audit rounds, so arm-clustering has evidence to work with
+    on the --audit-passes 1 runs that give it only one same-execution sample.
   files:
+  - plan_tool/review.py
   - plan_tool/convergence_diagnosis.py
+  - DATA_CONTRACT.md
+  - tests/test_review.py
   - tests/test_convergence_diagnosis.py
+  - tests/test_data_contract.py
   complexity: high
   change_type: feature
@@ -109,32 +116,66 @@ snapshot.
 plain input; nothing about its own logic is same-execution-specific. The
 mutual exclusion is entirely in what the *caller* (`review.py:8040`) currently
-feeds it. Building an equivalent mapping from history requires answering the
-"same target" question round-over-round without inventing new machinery for
-it: a step can be renumbered, split, or merged between rounds, and the existing
-`_matches` tiering exists precisely to survive that — it is the settled
-precedent, not a gap to redesign.
+feeds it, plus one persistence gap: the plan-audit prompt already emits an
+optional `[audit-step:N]` per-finding target and `_split_audit_step_evidence`
+already parses it, but the parsed value is diverted into the transient
+`_AuditTagObservation`/`observations_by_id` structures inside one
+`check_plan_audit_iterate` call and never reaches the saved
+`Recommendation`/`RunFinding` — both hardcode `step_id=None` for these sources,
+and `RunFinding`'s own docstring says the step a completeness finding is about
+is resolved by parsing `anchor`, which only incidentally carries a step number
+when the model's concept-slug happens to start with `stepN-`. Building a
+cross-round mapping therefore needs one new persisted field, plus answering the
+"same target" question round-over-round without inventing new *identity*
+machinery: a step can be renumbered, split, or merged between rounds, and the
+existing `_matches` tiering exists precisely to survive that — it is the
+settled precedent, not a gap to redesign.
 
 ## Architecture
 
-1. Restrict to the newest `window` same-`audit_stage` collapsed completeness
-   passes from `build_collapsed_completeness_passes`, mirroring
-   `classify_impact_recurrence` / `classify_edit_drift`'s own windowing — never
-   mix bare and detail-stage history in one consensus computation.
-2. For each pass, take its material findings (however materiality is computed
-   at that call site) and match each across the window via `_matches`. A
-   finding needs a `_matches` hit in ≥2 passes to be consensus-eligible at all,
-   mirroring the existing `len(sample_ids) < 2` guard.
-3. A matched finding's target per round is its own `step_id`. Consensus holds
-   only when every round in the match shares one target — identical to today's
+1. Persist the per-round step target. Add a new `Recommendation`/`RunFinding`
+   field (e.g. `audit_step_target: Optional[int]`) populated at the same parse
+   site that already computes it (`_split_audit_step_evidence`'s `target`,
+   currently diverted only into `_AuditTagObservation`), documented in
+   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
+   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   unaffected — they keep reading `observations_by_id` and the transient tag
+   directly.
+2. Restrict to the newest passes of a purpose-built window sized to fire at the
+   same 2-round minimum evidence bar as same-execution consensus
+   (`len(sample_ids) < 2`) — a new, smaller window constant, not
+   `classify_impact_recurrence` / `classify_edit_drift`'s shared
+   `WINDOW_SIZE=3` (sized for an unrelated "recurs without shrinkage" claim
+   that needs 3 points). Draw only same-`audit_stage` collapsed passes via
+   `build_collapsed_completeness_passes`; never mix bare and detail-stage
+   history in one window.
+3. Match findings across that window via the existing tiered `_matches` (step
+   focus → concept-slug anchor → fuzzy title) — no new identity scheme. A
+   finding is consensus-eligible only when it matches in every pass of the
+   window (for a 2-pass window this is the "≥2 passes" rule already stated).
+4. A matched finding's target per round is its new persisted
+   `audit_step_target` (point 1), never `RunFinding.step_id` (always `None`
+   for these sources). Consensus holds only when every round in the match
+   shares one non-`None` target — identical in spirit to today's
    `len(target_ids) != 1` fail-closed check.
-4. When a step's renumbering means no `step_id` continuity is even inferable
-   under `_matches` (the finding itself still matches by anchor/title, but its
-   target cannot be resolved to one committed step across the window), drop
-   that finding from consensus for the round pair rather than guessing a target
-   or asserting a broken arm. Fail-closed, not fail-loud — matching
-   `evaluate_arm_clustering`'s own posture when inputs are ambiguous.
-5. Feed the resulting `consensus_targets` and the newest round's committed
-   `declared_step_ids` / material finding set into `evaluate_arm_clustering`
+5. When a finding's per-round targets disagree, are missing, or a step's
+   renumbering breaks target continuity even though the finding still matches
+   by anchor/title, drop that finding from **both** the `consensus_targets`
+   mapping **and** the `material_finding_ids` set passed to the classifier —
+   never guess a target and never pass it through unresolved.
+   `evaluate_arm_clustering` returns `None` for the *entire* advisory the
+   moment any id in `material_finding_ids` lacks a resolved target
+   (`plan_tool/audit_shapes.py:238`), so the ids handed to it in point 6 must
+   already be exactly the resolved subset — not the newest round's full
+   material set.
+6. Feed the resulting `consensus_targets` (keyed by the newest round's finding
+   ids), that same resolved-subset `material_finding_ids`, and the newest
+   round's committed `declared_step_ids` into `evaluate_arm_clustering`
    unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+7. When the classifier has nothing to report — including when a previously-
+   firing arm's cross-round consensus becomes unresolvable — the render emits
+   nothing, the same silence `impact_recurrence` / `edit_drift` already use
+   for their own non-firing precondition. This is a stated decision, not an
+   open question (see Acceptance criteria): no separate "insufficient
+   evidence" line is added.
 
 ## References
@@ -142,7 +183,7 @@ precedent, not a gap to redesign.
 - [difflib — Helpers for computing deltas (Python 3 Standard Library)](https://docs.python.org/3/library/difflib.html) — Documents SequenceMatcher.ratio()'s [0, 1] similarity semantics and the 0.6 close-match convention behind the tier-3 fuzzy-title leg of _matches, which cross-round consensus reuses unchanged.
 - [collections.abc — Abstract Base Classes for Containers](https://docs.python.org/3/library/collections.abc.html) — Defines the Mapping ABC and its mixin cont
````

## 5. `security-check-command|2026-06-14T02:22:31Z|plan-plan-completeness-46a2db89`

**Cited step:** 1: Add security_audit.py orchestrator + plan-level prompt + shell_security_invoker seam

**Finding (plan-completeness, medium):** The severity-blocking policy requires security `LOW`/`NIT` to be non-blocking and forbids reusing `review.py:_CLAUDE_SEV

The severity-blocking policy requires security `LOW`/`NIT` to be non-blocking and forbids reusing `review.py:_CLAUDE_SEVERITY_MAP` (which folds `LOW`→`medium`→blocking), but the canonical `Recommendation.severity` set is `{critical, high, medium, nit, info}` — it has no `low`. The plan never states which canonical value a security `LOW` maps to (e.g. `nit` vs a newly introduced `low`), leaving rendering, ordering, and the non-blocking guarantee under-specified in step 1 (`_security_recommendations`).

**Suggested action:** specify the canonical severity value security `LOW` resolves to so the non-blocking policy is operationalized against the existing severity set

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index c2880123..0129b00a 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -21,5 +21,7 @@ steps:
 - id: 2
   title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit)
+    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
+    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
+    or vice versa (per-target scoping lands here, not deferred)
   files:
   - plan_tool/security_audit.py
@@ -53,6 +55,12 @@ steps:
 - id: 4
   title: 'Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
-    teach run_security_audit the reconcile target wired to it for plan⇆code security
-    drift'
+    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the
+    dispatch branch) wired to it for plan⇆code security drift, and construct the standalone
+    full plan⇄code surface drift scope (every step and its declared files in scope) so
+    security --reconcile runs on a tree with no recorded file drift — synthesize that
+    whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
+    step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
+    int / self-persisted security-reconcile.json output back into a SecurityAuditResult so
+    step 3''s cmd_security can render result.findings and persist via write_security_report'
   files:
   - plan_tool/cli/reconcile.py
@@ -142,5 +150,7 @@ steps:
     and prompts/security.md, populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
-    into the --iterate convergence apply loop'
+    into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
+    allowlist and apply-loop wiring (auto-apply is no longer advisory-only) since step
+    8 documents only the inert step-7 primitive'
   files:
   - plan_tool/prompts/security-plan.md
@@ -149,4 +159,5 @@ steps:
   - plan_tool/convergence.py
   - plan_tool/review_walk.py
+  - RUNBOOK.md
   - tests/test_security_audit.py
   - tests/test_convergence.py
@@ -176,9 +187,9 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. The `run_auto_reconcile_on_drift` hook's file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) stays the completeness/iteration-loop re-trigger mechanism (step 5), distinct from the standalone command's full-surface sweep. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit.
+Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit.
 
 The CLI subcommand lives in `cli/security_cmd.py` following the `review_cmd.py` pattern: a `register(subparsers) -> dict[str, Handler]` export and a `cmd_security(args) -> int` handler, added to the command-module registry and to `CANONICAL_COMMAND_ORDER` in `parser.py`, with `--fail-on-findings` support.
 
-Completeness integration adds a deterministic pre-pass plus a claude security dimension to `completeness_phases.py`: the security audit call is added alongside `_run_deterministic_checks()` but joins the conceptual (claude-backed) layer rather than the deterministic one; security findings are grouped in `_render_grouped_report()` as their own labeled section; and a `security` bucket is added to `_render_completeness_json()`. The completeness dimension reuses step 2's `<ts>-security.json` sidecar via `resolve_reusable_security` — on an unchanged plan+code fingerprint it reuses the saved report and skips the Claude pass, re-sampling (and persisting via `write_security_report`) only on a fingerprint miss. Cost is gated — the security dimension runs only when the plan touches security-relevant files/areas, or behind an explicit `--with-security` flag if always-on is too expensive — with the default decided in the detail step.
+Completeness integration adds a deterministic pre-pass plus a claude security dimension to `completeness_phases.py`: the security audit call is added alongside `_run_deterministic_checks()` but joins the conceptual (claude-backed) layer rather than the deterministic one; security findings are grouped in `_render_grouped_report()` as their own labeled section; and a `security` bucket is added to `_render_completeness_json()`. The completeness dimension reuses step 2's `<ts>-security.json` sidecar via `resolve_reusable_security` — on an unchanged plan+code fingerprint it reuses the saved report and skips the Claude pass, re-sampling (and persisting via `write_securit
````

## 6. `roadmap-revision-retention|2026-08-19T14:05:05Z|plan-plan-completeness-2635e6a8`

**Cited step:** 7: Document the removal snapshot, the decision reference, and the `closed` state (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all three existing "no `closed` member" sites (the schema block's `state` comment, the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather than adding fresh prose beside them — correct RUNBOOK.md's close-request table row and "Preserved by the gates" tables to match, and add a feedback-state vocabulary-completeness test to tests/test_roadmap_format.py mirroring `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` / `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such guard exists today for FeedbackState

**Finding (plan-completeness, medium):** The Overview and `## Not allowed` both state a reviewer "keeps full deletion rights over any row, closed included, exact

The Overview and `## Not allowed` both state a reviewer "keeps full deletion rights over any row, closed included, exactly as today; retention binds only the model's own edits" — deletion stays a real, load-bearing alternative to setting `state: closed`. But step 7's instruction is to correct the three existing "no `closed` member" sites "rather than adding fresh prose beside them," and one of those three is `ROADMAP_FORMAT.md`'s "**5. Closed** — the reviewer deletes the row" situation, whose worked example currently *is* the deletion walkthrough. Rewriting situation 5 to describe `state: closed` (the natural reading of "correct… rather than add fresh prose") drops the only documented example of plain deletion, and `RUNBOOK.md`'s close-request table row has the same shape — one row, one mechanism to describe. Nothing in step 7 or the acceptance criteria requires that the still-available deletion path stay documented once the primary "close" example changes to the state field.

**Suggested action:** broaden step 7 so both `ROADMAP_FORMAT.md`'s situation 5 and `RUNBOOK.md`'s close-request row document both live options — setting `state: closed` and plain deletion — rather than replacing the deletion example outright. Two prior findings (`[feedback-close-vocabulary]`, `[mode-review-namespace-collision]`'s predecessor concern about the "three sites" split) were re-traced against the current plan text: the "three sites" claim in `## Architecture` checks out exactly against `check_feedback_integrity`'s violation message, `prompts/roadmap-revision.md`'s carry-forward/"never do" text, and `_feedback_summary_lines`'s CLI guidance, with a clean, non-overlapping step 3/step 5 split — no further site turned up in a repo-wide sweep for "close by deleting" language. That finding reads as resolved by the current Architecture paragraph and isn't re-raised.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 71f49c1d..d7b2a424 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -11,9 +11,13 @@ steps:
 - id: 1
   title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
-    from the predecessor's own rendered row content — never model-authored — and
-    rendered back on every artifact rewrite
+    from the predecessor's own rendered row content — never model-authored — rendered
+    back on every artifact rewrite, and give `check_design_row_continuity` a
+    tampering-specific branch so an edited (not fabricated) carried removal is
+    rejected with a message naming the changed field and telling the model to
+    revert it, not drop the record
   intent: So a reader of a revised roadmap can see what the dropped row actually said
     instead of having to go read git, with no faithfulness question to gate because
-    the render layer derives the snapshot rather than the model paraphrasing it.
+    the render layer derives the snapshot rather than the model paraphrasing it, and
+    so an accidental edit to a carried removal gets a correction the model can act on.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -45,11 +49,14 @@ steps:
   - 1
   depends_on_notes:
-    1: Lands the omit-when-absent render idiom on _removal_mapping and the parse-unchanged
-      back-compat cases this second field reuses, and settles that both new fields
-      join whole-record carry identity.
+    1: Lands the omit-when-absent render idiom on _removal_mapping, the parse-unchanged
+      back-compat cases this second field reuses, and the tampering-specific branch
+      in check_design_row_continuity — step 2 extends that same branch to compare
+      decision_reference too, rather than building a second one.
 - id: 3
-  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
-    message and the revision prompt's state enum, carry-forward instruction, and
-    "never do" text — all three currently say the only close is deleting the row
+  title: Add `closed` to FeedbackState with a `_ANSWERED_FEEDBACK_STATE` self-mapping
+    (so a carried closed row's lookup doesn't raise `KeyError` and crash the revision),
+    and update the dropped-feedback gate's violation message and the revision
+    prompt's state enum, carry-forward instruction, and "never do" text — all three
+    currently say the only close is deleting the row
   intent: So a reviewer can retire a feedback request by setting its `state` field
     to `closed` in the file instead of deleting it, and the record of what was
@@ -86,8 +93,13 @@ steps:
       nothing to order last until closed rows can exist.
 - id: 5
-  title: 'Count closed rows in the roadmap summary and tell the operator to close
-    by setting `state: closed` rather than by deleting'
+  title: 'Count closed rows in both roadmap summary renderers — `_feedback_summary_lines`
+    (cli/roadmap_cmd.py, the run/revision post-run summary) and `_summary_feedback_counts`
+    / `render_roadmap_summary` (roadmap_view.py, the `--view summary` surface step
+    6 renames to `--mode history`) — and tell the operator to close by setting
+    `state: closed` rather than by deleting'
   intent: So the two hand-written state lists an operator actually reads stop disagreeing
-    with the state vocabulary the parser accepts.
+    with the state vocabulary the parser accepts, on both the post-run summary and
+    the renamed `--mode history` view whose whole rationale is surfacing retained
+    history.
   files:
   - plan_tool/roadmap_view.py
@@ -105,13 +117,17 @@ steps:
   title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
     choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
-    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
-    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
-    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text,
+    plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the
+    golden snapshot pinning it), and every literal `--mode review` example in
+    README.md, docs/ROADMAP_WALKTHROUGH.md, and docs/ARCHITECTURE.md — dropping
+    the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
     retain history rather than only pending review work, and no operator-facing
-    text anywhere still tells someone to pass a value the parser now rejects.
+    text anywhere — including the top-level `plan-tool --help` catalog — still
+    tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
   - plan_tool/cli/roadmap_cmd.py
+  - plan_tool/cli/__init__.py
   - docs/cli/roadmap.md
   - README.md
@@ -121,4 +137,5 @@ steps:
   - tests/test_roadmap_view.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/cli/package_surface_help.golden.txt
   complexity: medium
   change_type: refactor
@@ -130,6 +147,10 @@ steps:
     three existing "no `closed` member" sites (the schema block's `state` comment,
     the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
-    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
-    table row and "Preserved by the gates" tables to match
+    than adding fresh prose beside them — correct RUNBOOK.md's close-request table
+    row and "Preserved by the gates" tables to match, and add a feedback-state
+    vocabulary-completeness test to tests/test_roadmap_format.py mirroring
+    `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
+    `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
+    guard exists today for FeedbackState
   intent: So the review collections' schema is readable without opening the parser,
     which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer

````

## 7. `security-check-command|2026-06-17T10:27:53Z|plan-plan-completeness-cc68baa6`

**Cited step:** 3: Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile, --fail-on-findings) across all five registration seams; reuse-prompt wiring of resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred); --target code requires --step (single-step audit)

**Finding (plan-completeness, medium):** The interaction of `--step` with `--reconcile` is undefined across steps 3–4. `--target code` requires `--step` (single-

The interaction of `--step` with `--reconcile` is undefined across steps 3–4. `--target code` requires `--step` (single-step audit) while `--reconcile` derives its scope from the full plan⇄code surface (every step), but no step states whether `plan-tool security --reconcile --step <id>` is rejected, silently ignored, or scopes the reconcile to one step. An operator passing both gets unspecified behavior.

**Suggested action:** specify that `--step` is rejected (or ignored) with `--reconcile` so the whole-plan full-surface contract is unambiguous.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index aca1875e..f1c5187f 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -26,4 +26,9 @@ steps:
     code) via the filename suffix as well as fingerprint so a plan-axis caller never
     reuses a code-axis report or vice versa (per-target scoping lands here, not deferred);
+    the target="code" axis additionally scopes its lookup by step_id (mirroring the
+    reconcile family's per-step _find_saved_for_step, not the whole-plan resolve_reusable_audit
+    shape) because the <ts>-security-code.json suffix encodes only the target and not
+    the step, so two steps' code audits write same-suffix sidecars and a target-suffix-only
+    resolver would serve one step's saved code audit to another step's caller;
     a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do
     NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint
@@ -76,4 +81,5 @@ steps:
   - plan_tool/auto_reconcile.py
   - plan_tool/security_audit.py
+  - plan_tool/review.py
   - tests/test_auto_reconcile.py
   - tests/test_security_audit.py
@@ -113,7 +119,11 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/05-emit-relevance-gated-plan-tool-security.md
 - id: 6
-  title: Add a cheap, no-Claude relevance gate (keyword scan of plan title + step
-    titles + declared file paths) that decides whether the step-5 next-step pointer
-    is shown, plus a --no-security-hint suppression flag. A wrong verdict only shows
+  title: Add a cheap, no-Claude relevance gate (exact-token, not substring, scan of
+    plan title + step titles + declared file paths — each declared path first split
+    into tokens on the path separators and word boundaries `/`, `_`, `.`, and `-`,
+    so e.g. `plan_tool/cli/security_cmd.py` yields tokens {plan, tool, cli, security,
+    cmd, py} and the bare path string is never matched whole) that decides whether
+    the step-5 next-step pointer is shown, plus a --no-security-hint suppression flag.
+    A wrong verdict only shows
     or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes
     — it gates the pointer, never an audit pass
@@ -245,11 +255,11 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` is mutually exclusive with `--target`**: the two live in one argparse mutually-exclusive group (step 3), so `--reconcile` selects the internal `target="reconcile"` direction on its own and `plan-tool security --target code --reconcile <name>` is rejected at parse time rather than dispatching ambiguously — the orchestrator never sees a `--target`/`--reconcile` combination.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
 
-A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
+A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_sav
````

## 8. `security-check-command|2026-06-16T20:11:33Z|plan-plan-completeness-442d1693`

**Cited step:** 2: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis report or vice versa (per-target scoping lands here, not deferred); a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from resolve_reusable_audit applies only to the code/reconcile targets), so step 5's plan-fingerprint reuse engages instead of verdicting stale every run

**Finding (plan-completeness, medium):** The `--target plan` audit has no code surface, yet step 2's resolver gates freshness on both plan and code fingerprints 

The `--target plan` audit has no code surface, yet step 2's resolver gates freshness on both plan and code fingerprints (step 2's title carves out "a `target="plan"` save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target freshness on `saved.code_fingerprint_present`"), while step 3's `cmd_security` unconditionally computes and passes a `code_fingerprint` for every target including `plan`. No step states which fingerprint the *plan-target* reuse decision keys on once a consumer is wired, so a plan-only re-audit risks being marked stale by unrelated code drift.

**Suggested action:** pin in the plan that plan-target reuse freshness keys on the plan fingerprint alone (ignoring code drift) and name the step that enforces it at the call site.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 13cbe922..4fcd07cd 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -65,5 +65,6 @@ steps:
     whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
     step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
-    int / self-persisted security-reconcile.json output back into a SecurityAuditResult so
+    in-memory int / per-step findings output (with its per-step security-reconcile.json persistence
+    suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so
     step 3''s cmd_security can render result.findings and persist via write_security_report'
   files:
@@ -85,5 +86,7 @@ steps:
   title: 'Wire security dimension into completeness: conceptual-layer call + route
     security_recs through the existing findings-summarization/rollup gate before
-    rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of
+    rendering + grouped-report section + JSON security bucket + emit a `security --reconcile`
+    advisory pointer on code-only drift (cached `<ts>-security-plan.json` reused, not re-sampled)
+    (the completeness --iterate loop firing of
     run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
     drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
@@ -192,9 +195,9 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **plan-fingerprint-gated reuse**, not the hook: because that dimension is `target="plan"` and never folds code-level findings, it keys reuse on the *plan* fingerprint alone (plan markdown + detail bundle, via `compute_plan_fingerprint`) — reusing the saved `<ts>-security-plan.json` report and skipping the Claude pass whenever the plan/detail is unchanged, re-sampling only when the plan design itself changes, and treating code drift as an advisory pointer to `security --reconcile` rather than a re-sample trigger. This is distinct from the standalone command's full-surface sweep and is the cost lever that makes the dimension affordable now that it is on by default (see below). Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit. **One canonical sidecar and one writer for the reconcile direction:** the reuse-lookup surface is the single consolidated `<ts>-security-reconcile.json` written by `write_security_report(..., target="reconcile")` and resolved by `resolve_reusable_security(..., target="reconcile")` (which owns the `-security-reconcile` suffix); `run_auto_reconcile_on_drift`'s per-step `save_review(kind="security-reconcile")` sidecars and its `int` count are step-4-internal scratch, **not** a second reuse surface, and `resolve_reusable_reconcile` is not consulted for the security verb's reuse lookup. Step 4 aggregates the per-step drift findings `run_auto_reconcile_on_drift` produces into a single `SecurityAuditResult` (concatenating each step's findings, with `step_id` preserved on each `Recommendation`) and returns it; step 3's `cmd_security` renders `result.findings` and persists exactly that one consolidated report via `write_security_report(..., target="reconcile")`.
+Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **plan-fingerprint-gated reuse**, not the hook: because that dimension is `target="plan"` and never folds code-level findings, it keys reuse on the *plan* fingerprint alone (plan markdown + detail bundle, via `compute_plan_fingerprint`) — reusing the saved `<ts>-security-plan.json` report and skipping the Claude pass whenever the plan/detail is unchanged, re-sampling only when the plan design itself changes, and treating code drift as an advisory pointer to `security --reconcile` rather than a re-sample trigger. This is distinct from the standalone command's full-surface sweep and is the cost lever that makes the dimension affordable now that it is on by default (see below). Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit. **One canonical sidecar and one writer for the reconcile direction:** the single consolidated `<ts>-security-reconcile.json` written by `write_security_report(..., target="reconcile")` (step 3's `cmd_security`) and resolved by `resolve_reusable_security(..., target="reconcile")` (which owns the `-security-reconcile` suffix) is the **only** on-disk reconcile sidecar. To eliminate the double-write, step 4 invokes `run_auto_reconcile_on_drift` with its per-step `save_review(kind="security-reconcile")` persistence **suppressed** (e.g. a `persist=False`/no-op-save path) for the security verb, so no per-step `security-reconcile.json` is written a
````

## 9. `roadmap-terminal-error-contract|2026-09-21T16:36:10Z|plan-plan-correctness-aafdb9be`

**Cited step:** None: None

**Finding (plan-correctness, medium):** The terminal-status guarantee conflicts across Architecture, Risks, Testing, and Acceptance criteria: Architecture says 

The terminal-status guarantee conflicts across Architecture, Risks, Testing, and Acceptance criteria: Architecture says “Status reporting remains best-effort,” while Testing and Acceptance require every ordinary exception exit to emit “exactly one roadmap-level terminal status fact.” `plan_tool/roadmap.py:_emit_roadmap_fact` suppresses a callback failure, so a broken status sink produces no observable fact; define whether the requirement is one best-effort attempt or guaranteed delivery.

**Suggested action:** Define the terminal-status contract as one best-effort emission attempt and align the matrix, tests, risks, and acceptance criteria to that observable limit.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-terminal-error-contract.md b/docs/implementation-plans/2-roadmap-terminal-error-contract.md
index 61c01a4b..90dd8a92 100644
--- a/docs/implementation-plans/2-roadmap-terminal-error-contract.md
+++ b/docs/implementation-plans/2-roadmap-terminal-error-contract.md
@@ -40,11 +40,12 @@ steps:
     1: Defines the origin-specific exception meanings the shared reader must preserve.
 - id: 3
-  title: Preserve preflight and mid-run writer-guard origins while keeping publication
-    replacement and cleanup unchanged
+  title: Preserve writer-guard origins and terminal records before or during a roadmap run
   intent: Let the CLI distinguish invalid preflight use from a roadmap run that started
-    but could not finish.
+    but could not finish, while giving both dispositions a complete terminal record.
   files:
   - plan_tool/roadmap.py
+  - plan_tool/cli/roadmap_cmd.py
   - tests/test_roadmap.py
+  - tests/cli/test_roadmap_cmd.py
   complexity: medium
   change_type: feature
@@ -52,5 +53,6 @@ steps:
   - 1
   depends_on_notes:
-    1: Specifies the separate preflight-refusal and after-start failure dispositions.
+    1: Specifies the separate preflight-refusal and after-start failure dispositions,
+      including their terminal status, run-log ending, exit code, and crash behavior.
 - id: 4
   title: Normalize template read failures across stage authoring, feedback, local
@@ -161,6 +163,8 @@ selects the same terminal status, run-log ending, exit code, and crash behavior
 for equivalent template failures, emits the status exactly once after the last
 stage fact, and preserves the primary lifecycle's selected exit code rather
-than a default error code. Status reporting remains best-effort and cannot
-replace the original exception.
+than a default error code. A pre-lifecycle terminal-record boundary covers
+writer-guard refusal before a primary or materialization lifecycle starts; it
+records the matrix-selected disposition without pretending stages ran. Status
+reporting remains best-effort and cannot replace the original exception.
 
 ## Scope guardrails
@@ -231,7 +235,8 @@ human error, terminal status, run-log ending, exit code, and no crash file
 whether reached through fresh stage authoring, bounded feedback, local revision,
 or seed materialization. Prove the selected primary and materialization exit
-code matches the run-log ending, preflight and mid-run writer-guard failures
-select their different dispositions, and an unexpected exception still reaches
-the application crash path after exactly one roadmap terminal status fact.
+code matches the run-log ending; preflight and mid-run writer-guard failures
+select their different dispositions and each receives exactly one terminal
+record; and an unexpected exception still reaches the application crash path
+after exactly one roadmap terminal status fact.
 
 At the bare-plan gate, retain the disposition fields, origin boundary, and
@@ -248,5 +253,6 @@ each named producer route.
   lifecycle emits exactly one roadmap-level terminal status fact and a run-log
   ending consistent with its human message, selected return code, and crash
-  behavior.
+  behavior; a pre-lifecycle writer-guard refusal receives the same terminal
+  record without claiming a stage began.
 - Preflight and mid-run writer-guard failures remain distinguishable after they
   reach the CLI boundary.

````

## 10. `arm-clustering-cross-round-consensus|2026-08-12T21:33:43Z|plan-plan-correctness-2f3ce880`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-correctness, medium):** Step 1's Currency check (Implementation §3 point 5) drops a target "unless it is present in the caller's current `declar

Step 1's Currency check (Implementation §3 point 5) drops a target "unless it is present in the caller's current `declared_step_ids` *and* `step_statuses.get(target) is not StepStatus.DONE`." When `target` is a key missing from `step_statuses`, `.get(target)` returns `None`, and `None is not StepStatus.DONE` is `True` — the check silently passes as if the step were confirmed not-done, contradicting the plan's own stated principle in the same Architecture point 6 ("never guess a target and never pass an unresolved or stale one through"). Step 4's real wiring always builds `step_statuses` over every step in the plan so this can't happen in production, but step 1's classifier is a standalone function with `declared_step_ids` and `step_statuses` documented as "two independent parameters" and tested with independent fixture data — nothing in the plan states what a target-in-`declared_step_ids`-but-absent-from-`step_statuses` case should do, and step 1's own test roster has no case for it (only a case for a present, `DONE` status).

**Suggested action:** state in the Currency rule that a target present in `declared_step_ids` but absent as a key in `step_statuses` counts as unresolved status and must be dropped, not treated as not-done, and add a test for that case to step 1's roster alongside the existing done-status test.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index f245ca0c..7a8e5205 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -17,7 +17,7 @@ steps:
     `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
     and then discarded into a transient in-call structure before a review is saved),
-    then let a material finding earn a consensus step target from that persisted
-    value across separate audit rounds, so arm-clustering has evidence to work with
-    on the --audit-passes 1 runs that give it only one same-execution sample.
+    then let a material finding earn a consensus step target from that persisted value
+    across separate audit rounds, so arm-clustering has evidence to work with on the
+    --audit-passes 1 runs that give it only one same-execution sample.
   files:
   - plan_tool/review.py
@@ -29,4 +29,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
   status: current
 - id: 2
@@ -51,9 +52,14 @@ steps:
     1: the classifier function and its advisory record, which diagnose_convergence
       calls and the render lines read fields off
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
 - id: 3
   title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
   intent: Make the parsed plan reachable from cmd_convergence so the next step can
     read its committed steps without parsing the file a second time or copying the
-    best-effort try/except.
+    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
+    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
+    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
+    documented "always exits 0, never surfaces an error" contract survives the move
+    unchanged.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -61,13 +67,15 @@ steps:
   complexity: low
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
 - id: 4
   title: Pass committed step ids to the diagnosis from the convergence and completeness
     surfaces
   intent: Turn the classifier on for real operators by threading real committed step
-    ids *and* each step's current status (step 1's function signature accepts both as
-    parameters — a bare id list alone carries no status, and step 1's done-step drop
-    check needs it — but this step is what supplies real values from the plan's parsed
-    `Step` objects, not step 1) into it from the two places the sibling advisories
-    already print, so `plan-tool convergence` and completeness stderr both surface it.
+    ids *and* each step's current status (step 1's function signature accepts both
+    as parameters — a bare id list alone carries no status, and step 1's done-step
+    drop check needs it — but this step is what supplies real values from the plan's
+    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
+    already print, so `plan-tool convergence` and completeness stderr both surface
+    it.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -85,4 +93,5 @@ steps:
     3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
       the parse the stage lookup already did
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
 - id: 5
   title: Update the docs for the cross-round advisory and settle the backlog entries
@@ -92,8 +101,8 @@ steps:
     CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
     diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
-    omits `granularity`; both predate this plan and are wrong independent of it), so
-    correct both to the module''s full current set (`review_persistence`, `review`,
-    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step 2
-    adds — not only append the one new edge onto an already-wrong baseline. The
+    omits `granularity`; both predate this plan and are wrong independent of it),
+    so correct both to the module''s full current set (`review_persistence`, `review`,
+    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step
+    2 adds — not only append the one new edge onto an already-wrong baseline. The
     module''s own docstring paragraph is step 2''s fix, made where the import lands,
     not this step''s.'
@@ -110,4 +119,5 @@ steps:
     4: the shipped surfaces and the final import edge, so the docs describe what landed
       rather than what was proposed
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
 ---
 # Arm Clustering Cross Round Consensus
@@ -165,16 +175,33 @@ settled precedent, not a gap to redesign.
    Every cross-round consumer this plan builds reads `RunFinding`, not
    `Recommendation`, so missing the second site leaves the field permanently
-   `None` on everything this plan actually consumes. Document both fields in
-   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
-   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   `None` on everything this plan actually consumes. The two fields get two
+   different kinds of documentation, landed in **this same step**, not
+   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
+   persisted/serialized (round-trips via `save_review`), so it gets a row in
+   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
+   `impact`. `RunFinding` is not persisted on its own — its own docstring
+   calls it a flattening "from a saved report's recommendation list," and
+   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
+   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
+   there — so `RunFinding.audit_step_target` is documented inline in
+   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
+   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
+   section. This is the one new piece of persisted state this plan adds;
+   `evaluate_arm_clustering` and the same-execution consensus path are
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
 2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   checked **only against the newest round's copy** of that finding — the
-   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
-   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
-   and the same newest-round keying point 7 already uses for the output
-   mapping. A finding's severity/impact tag can differ across matched rounds;
+   checked **only against the newest round's copy** of that finding —
+   reusing only the stage-bar half of `classify_edit_drift`'s
+   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
+   newest-round keying point 7 already uses for the output mapping.
+   `_edit_drift_eligible` also runs a second check —
+   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
+   operator already declined between rounds — that this plan deliberately
+   does **not** reuse: Out of scope already refuses to gate cross-round
+
````

## 11. `security-check-command|2026-06-16T18:45:54Z|plan-plan-completeness-48e0b532`

**Cited step:** 9: Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md only (the per-step prompts/security.md is left unchanged so the --mode security per-step path is preserved), populate rec.anchor in _security_recommendations, seed SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active allowlist and apply-loop wiring (auto-apply is no longer advisory-only) since step 8 documents only the inert step-7 primitive

**Finding (plan-completeness, medium):** Step 9 is a `feature` step touching the riskiest surface in the plan (`convergence.py` + `review_walk.py` apply-loop wir

Step 9 is a `feature` step touching the riskiest surface in the plan (`convergence.py` + `review_walk.py` apply-loop wiring, the HIGH *Auto-apply danger* risk) yet ships with no detail file — its Tests, Acceptance, and implementation specifics exist only as four plan-body bullets, unlike every other code step. This is precisely the step whose apply-gate wiring [step9-apply-gate-bypass] is underspecified.

**Suggested action:** add a step-9 detail file pinning the apply-loop integration, its tests, and acceptance criteria.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 0129b00a..13cbe922 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -20,8 +20,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
-    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
-    or vice versa (per-target scoping lands here, not deferred)
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
+    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
+    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
+    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
+    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
+    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
+    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
+    plan-fingerprint reuse engages instead of verdicting stale every run
   files:
   - plan_tool/security_audit.py
@@ -79,6 +83,7 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + grouped-report
-    section + JSON security bucket (the completeness --iterate loop firing of
+  title: 'Wire security dimension into completeness: conceptual-layer call + route
+    security_recs through the existing findings-summarization/rollup gate before
+    rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of
     run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
     drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
@@ -148,5 +153,6 @@ steps:
 - id: 9
   title: 'Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md
-    and prompts/security.md, populate rec.anchor in _security_recommendations, seed
+    only (the per-step prompts/security.md is left unchanged so the --mode security per-step
+    path is preserved), populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
     into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
@@ -155,5 +161,4 @@ steps:
   files:
   - plan_tool/prompts/security-plan.md
-  - plan_tool/prompts/security.md
   - plan_tool/security_audit.py
   - plan_tool/convergence.py
@@ -183,15 +188,22 @@ Security is **already a per-step review mode**, but only at the per-step level:
 A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean completeness hook; downstream steps assume this unless the detail step pushes back to the user.
 
-A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits share the `kind="security"` bucket distinguished only by `source`, reuse resolution must scope by target/source as well as kind+fingerprint — a newest-by-kind lookup would serve a `target="code"` save to a plan-axis caller (completeness, step 5) or a plan save to `--target code` (step 3). A plan-audit reuse must never serve a code-audit report or vice versa.
+A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a plan-axis caller (completeness, step 5) can never resolve a `target="code"` save, nor `--target code` (step 3) a plan save — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa.
 
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a co
````

## 12. `security-check-command|2026-06-20T21:11:54Z|plan-plan-completeness-fdea3621`

**Cited step:** None: None

**Finding (plan-completeness, medium):** The `--target code` acceptance criteria cover the *missing*-`--step` rejection (rc 2 before any backend call) but never 

The `--target code` acceptance criteria cover the *missing*-`--step` rejection (rc 2 before any backend call) but never name the *unresolvable*-`--step` case — what `plan-tool security --target code <name> --step <bad-id>` does when the id points at no existing step. The criteria leave it undefined whether this fails cleanly or dispatches a backend call against a nonexistent step.

**Suggested action:** add a criterion that an unresolvable `--step` for `--target code` fails cleanly with a non-zero rc before invoking the backend, distinct from a completed audit

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 13. `security-check-command|2026-06-17T02:07:13Z|plan-plan-completeness-32b9914a`

**Cited step:** 3: Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile, --fail-on-findings) across all five registration seams; reuse-prompt wiring of resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred); --target code requires --step (single-step audit)

**Finding (plan-completeness, medium):** Step 3's title requires `--step` for `--target code` (single-step audit), but no step specifies the failure behavior whe

Step 3's title requires `--step` for `--target code` (single-step audit), but no step specifies the failure behavior when `--step` is omitted and no acceptance criterion locks it, leaving the contract unfalsifiable.

**Suggested action:** add a criterion that `security --target code` without `--step` fails cleanly (usage error, rc 2), distinct from a completed-audit exit.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 4fcd07cd..4166446e 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -13,4 +13,6 @@ steps:
   - plan_tool/prompts/security-plan.md
   - tests/test_security_audit.py
+  allowed_mentions:
+  - plan_tool/prompts/security.md
   complexity: high
   change_type: feature
@@ -20,12 +22,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
-    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
-    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
-    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
-    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
-    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
-    plan-fingerprint reuse engages instead of verdicting stale every run
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json
+    persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs
+    code) via the filename suffix as well as fingerprint so a plan-axis caller never
+    reuses a code-axis report or vice versa (per-target scoping lands here, not deferred);
+    a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do
+    NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint
+    staleness gate from resolve_reusable_audit applies only to the code/reconcile
+    targets)
   files:
   - plan_tool/security_audit.py
@@ -38,7 +40,7 @@ steps:
 - id: 3
   title: 'Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile,
-    --fail-on-findings) across all five registration seams, wiring resolve_reusable_security
-    into cmd_security so --target code reuses a saved report on a fingerprint hit; --target
-    code requires --step (single-step audit)'
+    --fail-on-findings) across all five registration seams; reuse-prompt wiring of
+    resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
+    --target code requires --step (single-step audit)'
   files:
   - plan_tool/cli/app.py
@@ -58,14 +60,17 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/03-register-security-subcommand-cli.md
 - id: 4
-  title: 'Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
-    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the
-    dispatch branch) wired to it for plan⇆code security drift, and construct the standalone
-    full plan⇄code surface drift scope (every step and its declared files in scope) so
-    security --reconcile runs on a tree with no recorded file drift — synthesize that
-    whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
-    step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
-    in-memory int / per-step findings output (with its per-step security-reconcile.json persistence
-    suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so
-    step 3''s cmd_security can render result.findings and persist via write_security_report'
+  title: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
+    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add
+    the dispatch branch) wired to it for plan⇆code security drift, and construct the
+    standalone full plan⇄code surface drift scope (every step and its declared files
+    in scope) so security --reconcile runs on a tree with no recorded file drift —
+    synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map
+    over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's
+    in-memory int / per-step findings output (with its per-step security-reconcile.json
+    persistence suppressed so write_security_report is the sole on-disk writer) back
+    into a SecurityAuditResult so step 3's cmd_security can render result.findings
+    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
+    the reconcile family uses resolve_saved_review in review_persistence
   files:
   - plan_tool/cli/reconcile.py
@@ -77,4 +82,7 @@ steps:
   creates:
   - plan_tool/prompts/security-reconcile.md
+  allowed_mentions:
+  - plan_tool/prompts/detail-reconcile.md
+  - plan_tool/prompts/security.md
   complexity: medium
   change_type: feature
@@ -84,30 +92,37 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + route
-    security_recs through the existing findings-summarization/rollup gate before
-    rendering + grouped-report section + JSON security bucket + emit a `security --reconcile`
-    advisory pointer on code-only drift (cached `<ts>-security-plan.json` reused, not re-sampled)
-    (the completeness --iterate loop firing of
-    run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
-    drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
+  title: Emit a relevance-gated `plan-tool security` next-step pointer at the end
+    of `detail` and `completeness` — NOT a security dimension inside completeness.
+    Append a suggestion line via the existing _print_next_steps helper (cli/console.py)
+    in cli/authoring.py:cmd_detail (after the existing review/run/jira Next-steps
+    block) and in cli/completeness_phases.py:_persist_and_present_report (both the
+    --iterate summary path and the audit-only path). Completeness does NOT invoke
+    run_security_audit, render a Security section in _render_grouped_report, or add
+    a security bucket to _render_completeness_json — security stays a standalone command
+    the pointer advertises. Unconditional emission lands here; step 6 adds the relevance
+    gate
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
-  - tests/test_cli.py
+  - tests/cli/test_authoring.py
   - tests/cli/test_completeness_cmd.py
-  complexity: high
+  allowed_mentions:
+  - tests/cli/test_authoring_cmds.py
+  complexity: medium
   change_type: feature
   depends_on:
-  - 1
-  - 2
-  - 4
-  detail: docs/implementation-plans/plan-details/security-check-command/05-wire-security-dimension-completeness.md
+  - 3
+  detail: docs/implementation-plans/plan-details/security-check-command/05-emit-relevance-gated-plan-tool-security.md
 - id: 6
-  title: Add cost relevance gate + --with-security flag controlling whether the completeness
-    security dimension runs
+  title: Add a cheap, no-Claude relevance gate (keyword scan of plan title + step
+    titles + declared file paths) that decides whether the step-5 next-step pointer
+    is shown, plus a --no-security-hint suppression flag. A wrong verdict only shows
+    or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes
+    — it gates the pointer, never an audit pass
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
   - plan_tool/cli/parser.py
+  - plan_tool/security_audit.py
   - tests/cli/test_completeness_cmd.py
   complexity: medium
@@ -115,8 +130,11 @@ steps:
   depends_on:
   - 5
-  detail: docs
````

## 14. `security-check-command|2026-06-20T21:11:54Z|plan-plan-completeness-b9380f5f`

**Cited step:** 4: Add a security-reconcile run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's in-memory int / per-step findings output (with its per-step security-reconcile.json persistence suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report; because the generalized hook's best-effort loop skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit) and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default — so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(..., target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile; the reconcile family uses resolve_saved_review in review_persistence

**Finding (plan-completeness, medium):** Step 4's reconcile sweep is best-effort — it `continue`s past a launcher-error/non-zero-exit step with only a stderr not

Step 4's reconcile sweep is best-effort — it `continue`s past a launcher-error/non-zero-exit step with only a stderr note — and surfaces coverage solely as a human-visible `skipped_steps` count that step 3's `cmd_security` renders alongside findings. Nothing threads that count into the exit code: `--fail-on-findings` flips only on blocking (`MEDIUM`/`HIGH`/`CRITICAL`) findings, so a `security --reconcile` sweep that audited 7 of 10 steps and found nothing blocking exits 0 even under `--fail-on-findings`. The Risks section names partial coverage "false assurance, the worst failure mode for a security verb," yet the mitigation reaches only a human reading stderr — a CI gate parsing rc cannot distinguish a fully-covered clean sweep from a partial one, and no acceptance criterion locks in any partial-coverage behavior at all.

**Suggested action:** decide and state whether `skipped_steps > 0` is a failure-to-complete that flips the rc (or add a flag/criterion that lets an automated gate detect partial coverage), so the "false assurance" risk is mitigated for machine consumers, not only humans.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 15. `security-check-command|2026-06-16T18:45:54Z|plan-plan-completeness-225373aa`

**Cited step:** None: None

**Finding (plan-completeness, medium):** The Architecture and *Cost/latency* risk repeatedly promise that, on code drift with an unchanged plan, the completeness

The Architecture and *Cost/latency* risk repeatedly promise that, on code drift with an unchanged plan, the completeness dimension reuses the cached report and "emits an advisory pointing at `security --reconcile`," but no step's detail renders that advisory and no acceptance criterion locks it in — the concept is orphaned (and is moot until [completeness-reuse-keying] wires the reuse resolver that surfaces `drifted_code`).

**Suggested action:** assign the advisory-pointer rendering to step 5 (or a named step) and add a criterion that a code-only change emits the `security --reconcile` pointer rather than re-sampling.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 0129b00a..13cbe922 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -20,8 +20,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
-    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
-    or vice versa (per-target scoping lands here, not deferred)
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
+    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
+    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
+    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
+    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
+    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
+    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
+    plan-fingerprint reuse engages instead of verdicting stale every run
   files:
   - plan_tool/security_audit.py
@@ -79,6 +83,7 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + grouped-report
-    section + JSON security bucket (the completeness --iterate loop firing of
+  title: 'Wire security dimension into completeness: conceptual-layer call + route
+    security_recs through the existing findings-summarization/rollup gate before
+    rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of
     run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
     drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
@@ -148,5 +153,6 @@ steps:
 - id: 9
   title: 'Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md
-    and prompts/security.md, populate rec.anchor in _security_recommendations, seed
+    only (the per-step prompts/security.md is left unchanged so the --mode security per-step
+    path is preserved), populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
     into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
@@ -155,5 +161,4 @@ steps:
   files:
   - plan_tool/prompts/security-plan.md
-  - plan_tool/prompts/security.md
   - plan_tool/security_audit.py
   - plan_tool/convergence.py
@@ -183,15 +188,22 @@ Security is **already a per-step review mode**, but only at the per-step level:
 A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean completeness hook; downstream steps assume this unless the detail step pushes back to the user.
 
-A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits share the `kind="security"` bucket distinguished only by `source`, reuse resolution must scope by target/source as well as kind+fingerprint — a newest-by-kind lookup would serve a `target="code"` save to a plan-axis caller (completeness, step 5) or a plan save to `--target code` (step 3). A plan-audit reuse must never serve a code-audit report or vice versa.
+A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a plan-axis caller (completeness, step 5) can never resolve a `target="code"` save, nor `--target code` (step 3) a plan save — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa.
 
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a co
````

## 16. `roadmap-revision-retention|2026-08-19T14:05:05Z|plan-plan-correctness-3cfd05c3`

**Cited step:** 4: Add a gate rejecting a revision whose `feedback` collection places a `closed` row before a non-`closed` row, and tell the model in the revision prompt to keep closed rows last when it re-emits the collection

**Finding (plan-correctness, medium):** Step 4's gate only rejects a *model-emitted revision* that places a closed row before a non-closed row, and the Architec

Step 4's gate only rejects a *model-emitted revision* that places a closed row before a non-closed row, and the Architecture section confirms nothing sorts the `feedback` collection today ("No existing mechanism orders the `feedback` collection at all"). A reviewer who hand-edits a mid-list row's `state` to `closed` — the plan's own described closing move — leaves that row in its original position on disk until a later revision happens to run and the model re-emits the collection sorted; if no later revision ever runs, the row stays out of order indefinitely. The acceptance criteria state the ordering as an unconditional property ("renders after every non-`closed` row in the `feedback` collection"), but the plan names no route that fixes position on a reviewer's own edit.

**Suggested action:** state whether the ordering guarantee is scoped to "after the next revision" or specify a mechanical, render-time sort independent of the model — matching step 1's mechanical-snapshot precedent — so a reviewer's direct edit can't leave the artifact violating its own acceptance criterion.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 71f49c1d..d7b2a424 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -11,9 +11,13 @@ steps:
 - id: 1
   title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
-    from the predecessor's own rendered row content — never model-authored — and
-    rendered back on every artifact rewrite
+    from the predecessor's own rendered row content — never model-authored — rendered
+    back on every artifact rewrite, and give `check_design_row_continuity` a
+    tampering-specific branch so an edited (not fabricated) carried removal is
+    rejected with a message naming the changed field and telling the model to
+    revert it, not drop the record
   intent: So a reader of a revised roadmap can see what the dropped row actually said
     instead of having to go read git, with no faithfulness question to gate because
-    the render layer derives the snapshot rather than the model paraphrasing it.
+    the render layer derives the snapshot rather than the model paraphrasing it, and
+    so an accidental edit to a carried removal gets a correction the model can act on.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -45,11 +49,14 @@ steps:
   - 1
   depends_on_notes:
-    1: Lands the omit-when-absent render idiom on _removal_mapping and the parse-unchanged
-      back-compat cases this second field reuses, and settles that both new fields
-      join whole-record carry identity.
+    1: Lands the omit-when-absent render idiom on _removal_mapping, the parse-unchanged
+      back-compat cases this second field reuses, and the tampering-specific branch
+      in check_design_row_continuity — step 2 extends that same branch to compare
+      decision_reference too, rather than building a second one.
 - id: 3
-  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
-    message and the revision prompt's state enum, carry-forward instruction, and
-    "never do" text — all three currently say the only close is deleting the row
+  title: Add `closed` to FeedbackState with a `_ANSWERED_FEEDBACK_STATE` self-mapping
+    (so a carried closed row's lookup doesn't raise `KeyError` and crash the revision),
+    and update the dropped-feedback gate's violation message and the revision
+    prompt's state enum, carry-forward instruction, and "never do" text — all three
+    currently say the only close is deleting the row
   intent: So a reviewer can retire a feedback request by setting its `state` field
     to `closed` in the file instead of deleting it, and the record of what was
@@ -86,8 +93,13 @@ steps:
       nothing to order last until closed rows can exist.
 - id: 5
-  title: 'Count closed rows in the roadmap summary and tell the operator to close
-    by setting `state: closed` rather than by deleting'
+  title: 'Count closed rows in both roadmap summary renderers — `_feedback_summary_lines`
+    (cli/roadmap_cmd.py, the run/revision post-run summary) and `_summary_feedback_counts`
+    / `render_roadmap_summary` (roadmap_view.py, the `--view summary` surface step
+    6 renames to `--mode history`) — and tell the operator to close by setting
+    `state: closed` rather than by deleting'
   intent: So the two hand-written state lists an operator actually reads stop disagreeing
-    with the state vocabulary the parser accepts.
+    with the state vocabulary the parser accepts, on both the post-run summary and
+    the renamed `--mode history` view whose whole rationale is surfacing retained
+    history.
   files:
   - plan_tool/roadmap_view.py
@@ -105,13 +117,17 @@ steps:
   title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
     choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
-    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
-    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
-    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text,
+    plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the
+    golden snapshot pinning it), and every literal `--mode review` example in
+    README.md, docs/ROADMAP_WALKTHROUGH.md, and docs/ARCHITECTURE.md — dropping
+    the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
     retain history rather than only pending review work, and no operator-facing
-    text anywhere still tells someone to pass a value the parser now rejects.
+    text anywhere — including the top-level `plan-tool --help` catalog — still
+    tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
   - plan_tool/cli/roadmap_cmd.py
+  - plan_tool/cli/__init__.py
   - docs/cli/roadmap.md
   - README.md
@@ -121,4 +137,5 @@ steps:
   - tests/test_roadmap_view.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/cli/package_surface_help.golden.txt
   complexity: medium
   change_type: refactor
@@ -130,6 +147,10 @@ steps:
     three existing "no `closed` member" sites (the schema block's `state` comment,
     the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
-    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
-    table row and "Preserved by the gates" tables to match
+    than adding fresh prose beside them — correct RUNBOOK.md's close-request table
+    row and "Preserved by the gates" tables to match, and add a feedback-state
+    vocabulary-completeness test to tests/test_roadmap_format.py mirroring
+    `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
+    `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
+    guard exists today for FeedbackState
   intent: So the review collections' schema is readable without opening the parser,
     which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer

````

## 17. `roadmap-candidate-same-batch-relations|2026-09-28T12:27:10Z|plan-plan-correctness-b4d90c90`

**Cited step:** 1: Allow exact same-batch relation endpoints while preserving row replacement and removal

**Finding (plan-correctness, medium):** Step 1 contradicts the existing batch lifecycle it says must remain unchanged. Architecture says:

Step 1 contradicts the existing batch lifecycle it says must remain unchanged. Architecture says:

  ```
  do not change candidate classification, review/promotion semantics, canonical artifact writing, feedback lifecycle effects, or seed effects.
  ```

  Yet Testing and the step’s candidate-run test require no “feedback-state … publication.” `roadmap_candidate_run:_store_batch_candidate` always calls `_apply_batch_ledger_patch`, which changes each admitted reviewer item to `awaiting-review` and records its proposal. The test could either require an impossible no-state-write result or incorrectly change the established lifecycle.

**Suggested action:** State that candidate storage retains the existing admitted-item ledger transition while publishing no canonical roadmap artifact, accepted head, or seed, and align the plan and candidate-run assertion to that boundary.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md b/docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md
index 752fb543..cbb0a776 100644
--- a/docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md
+++ b/docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md
@@ -25,4 +25,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-same-batch-relations/01-allow-exact-same-batch-relation.md
   status: current
 - id: 2
@@ -36,4 +37,5 @@ steps:
   depends_on:
   - 1
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-same-batch-relations/02-remove-resolved-candidate-relation-bug.md
 ---
 # Roadmap Candidate Same Batch Relations
diff --git a/docs/implementation-plans/plan-details/roadmap-candidate-same-batch-relations/01-allow-exact-same-batch-relation.md b/docs/implementation-plans/plan-details/roadmap-candidate-same-batch-relations/01-allow-exact-same-batch-relation.md
new file mode 100644
index 00000000..d3300814
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-candidate-same-batch-relations/01-allow-exact-same-batch-relation.md
@@ -0,0 +1,96 @@
+# Step 1 — Allow exact same-batch relation endpoints while preserving row replacement and removal
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+Allow a validated candidate batch to use an exact row added by that same batch as a declared-relation endpoint. Update `plan_tool/roadmap_candidate.py:_validate_relation_authority` while retaining operation admission in `_validate_operation_authority` and the existing candidate assembly flow in `materialize_candidate`. Add focused materialization coverage in `tests/test_roadmap_candidate.py` and a batch-run regression in `tests/test_roadmap_candidate_run.py`. On green, coherent multi-feedback batches reach the existing inert structural-candidate route without publishing canonical roadmap state.
+
+## Table of Contents
+
+- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
+- [Table of Contents](#table-of-contents) — Routes to each section.
+- [Why](#why) — The current authority gap and its impact.
+- [Input](#input) — Candidate operation and context contracts this step reads.
+- [Files (creates vs edits)](#files-creates-vs-edits) — The limited implementation footprint.
+- [Implementation](#implementation) — Required authority boundary and recommended approach.
+- [Tests](#tests) — Focused regression coverage and green gate.
+- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
+- [References](#references) — Source bug and unchanged lifecycle contract.
+- [Applicable guardrails](#applicable-guardrails) — Scope limits for this change.
+
+## Why
+
+`plan_tool/roadmap_candidate.py:_validate_relation_authority` currently requires changed relation endpoints to be predecessor members, so an admitted batch cannot connect an existing changed row to a valid row that the same batch adds. That blocks the normal multi-feedback structural case even after every operation has passed typed validation and feedback binding. The fix must allow only the exact added identity in the same normalized candidate, while keeping predecessor-membership and reached-context rules fail-closed for everything else.
+
+## Input
+
+- **Normalized operations:** `materialize_candidate` prepares the parsed `CandidateDelta.operations` before authority validation. This step depends on the exact `CandidateAddRow`, `CandidateReplaceRow`, and `CandidateRemoveRow` identities and their admitted `feedback_id` values.
+- **Candidate artifacts:** `_validate_relation_authority` compares `extract_declared_relations` over immutable predecessor artifacts and the fully applied candidate artifacts. The candidate artifacts are the source for confirming that an allowed added endpoint actually exists after application.
+- **Capsule authority:** `_full_member_authority`, `CandidateContextCapsule.full_members`, and `CandidateContextCapsule.relation_evidence` remain the authority source for predecessor rows and reached anchors. Same-batch additions must not expand this context.
+
+## Files (creates vs edits)
+
+- **New files:** None.
+
+- **Existing files (edits only):**
+  - `plan_tool/roadmap_candidate.py` — extend `_validate_relation_authority` so exact same-candidate additions can satisfy relation endpoint and added-owner anchor checks without weakening operation authority.
+  - `tests/test_roadmap_candidate.py` — replace the predecessor-only sibling regression with exact-linkage, rejection, and operation-order materialization cases.
+  - `tests/test_roadmap_candidate_run.py` — cover the batch proposal route reaching the existing structural candidate surface without publication.
+
+## Implementation
+
+- **Keep typed-operation authority first.** Leave `materialize_candidate` ordering intact: `_prepare_operations` and `_validate_operation_authority` must reject malformed, colliding, wrongly typed, or unbound operations before relation authority considers a same-batch endpoint.
+
+- **Bind the exception to an exact addition.** In `plan_tool/roadmap_candidate.py:_validate_relation_authority`, treat a missing predecessor endpoint as available only when a distinct `CandidateAddRow` in the same prepared operation set creates its exact artifact key, typed row identity, and row id. Do not use a row-id-only match.
+
+- **Preserve independent feedback traceability.** The relation-owning operation and endpoint-addition operation may carry different admitted `feedback_id` values. Their existing operation-level bindings are the authority record; do not add a relation-level feedback protocol.
+
+- **Update both relation guards together.** The predecessor-membership branch and the added-row reached-anchor branch must both recognize the same exact same-batch endpoint rule. A partial change leaves added-owner-to-added-endpoint relations rejected even when existing-owner-to-added-endpoint relations work.
+
+- **Keep predecessor authority unchanged.** When an endpoint is found in predecessor artifacts, retain the existing full-content capsule-membership requirement through `_predecessor_relation_members`. A same-batch addition must not become a general context anchor for unrelated added rows.
+
+- **Retain removal and replacement behavior.** Keep the incident-relation removal check for `CandidateRemoveRow`, and keep relation ownership tied to an owning add, replace, or remove operation as `_validate_relation_authority` already requires. The new endpoint allowance must not authorize a relation whose owner lacks its own valid operation.
+
+- **Keep validation and lifecycle ownership unchanged.** Let `_assemble_candidate_artifacts`, `check_complete_roadmap_gates`, `_classify_validated_operations`, and the existing batch-candidate path decide validity and structural routing after authority succeeds. Do not alter review, promotion, accepted-head, feedback-state, seed, or canonical-artifact behavior.
+
+- **Use materialization-level cases for the core rule.** Helper-only tests are not enough because correctness depends on prepared operations, candidate application, relation extraction, complete gates, and structural classification working together.
+
+## Tests
+
+### Tests for this step
+
+- `test_candidate_existing_owner_can_relate_to_exact_same_batch_added_endpoint` — materializes a gate-clean structural candidate where an admitted replacement points to an endpoint created by another admitted `add-row`, including distinct feedback bindings.
+- `test_candidate_added_owner_can_relate_to_exact_same_batch_added_endpoint` — materializes a gate-clean structural candidate where an added owner declares a relation to an exact same-batch added endpoint.
+- `test_candidate_same_batch_relation_endpoint_is_operation_order_independent` — verifies both operation orders produce the same successful candidate result.
+- `test_
````

