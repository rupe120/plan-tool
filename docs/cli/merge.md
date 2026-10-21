# `plan-tool merge`

## Usage

```
plan-tool merge [-h] [-y] [--max-iterations N] [--iteration-budget SECONDS] [--time-budget SECONDS] [--max-stall-rounds N] [--allow-drift] [--no-auto-reconcile-on-drift] [--no-triage] [--include-info] [--no-collision-sidecar] --steps ID [--title TITLE] [--iterate | --no-iterate] [--no-detail] [--no-completeness] [--dry-run] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--max-iterations` `N` | `3` | cap the convergence loop at N iterations even if findings keep changing (default: 3). Ignored when --no-iterate is set. |
| `--iteration-budget` `SECONDS` | `1800` | debounced no-progress deadline in seconds: stop the convergence loop only once SECONDS pass with no forward progress at all (default: 1800). Resets on every round and every apply_finding call, so one long claude call — even 15-20+ minutes — never trips it on its own; see --time-budget for a true total-elapsed cap. Ignored when --no-iterate is set. |
| `--time-budget` `SECONDS` | — | cooperative wall-clock cap (#123): stop the convergence loop cleanly at the next round boundary once SECONDS of total elapsed time pass — even while still converging — so a long op lands before an external execution ceiling instead of being killed mid-call. Exits 0 with a resume hint. Unlike --iteration-budget (a no-progress stall deadline), this is a hard total-elapsed cap. Falls back to PLAN_TOOL_TIME_BUDGET; default off. Ignored under --no-iterate. |
| `--max-stall-rounds` `N` | `2` | stop the convergence loop after N consecutive rounds whose open-finding count fails to shrink (default: 2). This is the ID-agnostic backstop for a subjective claude audit that re-phrases the same findings each round (fresh ids defeat the marginal / converged checks). Pass 0 to disable. Ignored when --no-iterate is set. |
| `--allow-drift` | off | opt back into the legacy 'warn but proceed' behavior when a watched file's content changes mid-iteration. Default: the loop checks drift BEFORE each apply (halts without spending claude tokens if drift detected) AND AFTER (keeps the apply's edits but halts subsequent applies if drift happened during the apply call). Token-preserving by design -- no revert, just halt + flag for `git diff` review (task #30). Pass --allow-drift only when you're sure the drift is expected (e.g. an automated formatter touching files in step.files during iteration). |
| `--no-auto-reconcile-on-drift` | on | skip the auto-reconcile pass that fires when drift halts the iteration loop. Default: when drift is detected, plan-tool runs `reconcile` against the step(s) that own the drifted file(s), saves the findings, and prints a structured summary inline with the halt (Lesson 13: audit beats observe). Pass this flag to suppress that extra claude call -- useful in CI runs that prefer a minimal stderr footprint, or when you'll inspect drift manually via `git diff` and `plan-tool run --mode reconcile`. |
| `--no-triage` | on | skip the impact-weighted triage gate on findings. Default: when a finding carries impact/complexity tags (the plan-audit prompt's trailing ``(impact=…, complexity=…)`` on conceptual findings; the reconcile prompt's ``Impact:`` / ``Complexity:`` fields), the iteration loop skips applies whose complexity strictly exceeds their impact (low+medium, low+high, medium+high) -- those findings are reported on stderr and dropped from the open-set so convergence short-circuits when only triaged findings remain. Findings without triage tags (deterministic checks, untagged output) default to apply. Pass this flag to force-apply every finding regardless of triage tags -- useful for completeness sweeps where you want to land every applicable edit. |
| `--include-info` | off | apply info-severity findings too. Default: info findings are advisory (a concept too vague to audit, a heuristic hit, a detail-only path) and are excluded from the apply loop -- they're still reported in the deferred summary, just not auto-applied. Pass this to spend claude tokens applying them as well. |
| `--no-collision-sidecar` | on | skip the change-collision sidecar pause when drift fires during apply_finding. Default: when drift is detected post-apply, plan-tool saves claude's edits to `<stem>-change-collision<ext>` next to each modified original, restores originals to pre-apply state, and pauses interactively for the user to merge with their preferred tool (vimdiff, `code --diff`, meld, etc.). Pressing Enter at the prompt continues the iteration loop against the merged state; Ctrl-D / typing 'abort' halts as today. Pass this flag to revert to the legacy 'keep claude's edits on disk, review via git diff' behavior -- useful when scripting or piping to a CI consumer that doesn't expect sidecar files. Headless runs (-y or non-TTY) auto-skip the pause and fall through to halt regardless of this flag, since there's no human to merge. |
| `--steps` `ID` | — | id of a step to fold into the merge; pass --steps at least twice for a contiguous dependency chain (e.g. --steps 3 --steps 4). The set collapses to a single step at the lowest id and the plan renumbers to a contiguous 1..N. |
| `--title` `TITLE` | — | optional title for the merged step; omit to let the orchestrator derive one from the folded members' titles. |
| `--iterate`, `--no-iterate` | on | run the per-step detail-quality loop on the merged step and the iterate convergence loop in the completeness tail. Default ON -- pass --no-iterate for one-shot authoring + an audit-only completeness report. |
| `--no-detail` | on | merge only: renumber + combine-and-archive detail files, but don't re-author the merged step's body or run the completeness tail (author it later with `plan-tool detail <name>`). |
| `--no-completeness` | on | skip the conceptual completeness audit that otherwise runs after the merged step is authored cleanly. Pass --no-iterate instead to keep it as an audit-only report with no apply calls. |
| `--dry-run` | off | preview the merge — print the old→new step renumber map and the resulting plan — without writing the plan, renaming/archiving detail files, or authoring/auditing anything. |
