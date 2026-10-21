# Verified plan-tool orchestration facts for the Integration MVP (2026-08-28)

**Status (2026-09-08):** still-valid measured behavior, with one retirement: the `--revise-feedback` row describes a route that enrolled roadmaps no longer use; feedback enters the immutable candidate route (`backlog-arc-integration-mvp.md` § "Current goal").

Measured against plan-tool-1 (identical roadmap code to canonical ca6270aa),
run on copies of Integration's real tree. These constrain what the construction
phase can and cannot ask of plan-tool.

| Fact | Evidence | MVP consequence |
| --- | --- | --- |
| `roadmap` needs **no git repository** — it ran to the backend in a bare directory. | `run_roadmap` in a non-git dir reached the invoker. | Construction can produce roadmap → seeds → plans → Jira stories in a plain workspace with no repo. A repo is needed only for `run` (code) and `--commit`. |
| The brief must be a **file inside the workspace**, recorded once in `source.json`; a later run with a different path is refused (`already grounded in <path>`). | Verified refusal message. | The accepted inception output is written to the workspace as the brief, once. Re-running with a revised brief needs a new slug. |
| Each stage write publishes its **artifact and baseline together**; a fresh slug needs no prior baseline. | `publish_stage_artifact`; fresh-slug run reached backend. | A Integration-created roadmap is self-baselining — the drift trap that froze `roadmap integration` cannot occur unless something hand-edits a canonical artifact. **The API must never write to a canonical artifact directly.** |
| Revision is bounded and per-row: `--revise-feedback <artifact>:<id>` makes exactly one backend request. | `docs/cli/roadmap.md`; Integration run logs. | Browser review maps to one feedback row per request — not a free-form chat over the artifact. |
| `--from-stage` on a drifted roadmap fails closed as `stage-invalid` with **no backend call**. | Ran from_stage 1/2/4 on a real-tree copy. | Failed re-entry is cheap; the UI can attempt and report without cost. |
| `--materialize` / `--apply` / `create` need **no baseline admission**. | `materialize_plan_seed` uses `_load_stage_artifact`; apply reads `04-roadmap.md` off disk. | The forward path is independent of the revision path. |
| `--apply` is **refuse-by-default** on an existing `plan-seeds/<id>.md`. | Real-tree apply returned `refused`, 9 collisions. | Per-project workspaces avoid collisions; a shared seed directory does not. |
| `jira` exports epics + stories as Markdown/JSON with an epic config and per-plan tags; no tracker API call. | `docs/cli/jira.md`, `JIRA_FORMAT.md`. | The "Jira epic and story" option is an export artifact for review/paste, matching the 2026-08-28 no-API-write decision. |
| Every run writes a JSONL event stream under `.plan-tool/runs/<slug>/` (`run_start`, `phase_start`, `claude_call_progress`, `claude_stream_event`, `phase_end`, `run_end`). | `run_log.py`; Integration's own run logs. | The browser status stream needs **no new plan-tool surface** for the MVP: the worker tails this file and republishes. Integration's `execution-status-event` maps onto it directly. |
| Long calls are the norm; gate failures retry inside a stage; `stage-exhausted` is a real outcome. | Integration run logs across 2026-08-11/12/24. | Construction must model roadmap generation as a durable job with retry-visible status, never a request-response chat turn. |
