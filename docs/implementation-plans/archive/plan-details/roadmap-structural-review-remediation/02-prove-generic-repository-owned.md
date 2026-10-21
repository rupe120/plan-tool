# Step 2 — Prove a generic repository-owned evaluator probe works on the host before its Seatbelt denial and fail closed when that proof is unavailable

## Summary

Make `plan_tool/roadmap_structural_revision_run.py` prove a repository-owned probe file is usable on the ordinary host before treating Seatbelt failures on that same file as isolation evidence. Update the focused evaluator tests in `tests/test_roadmap_structural_revision_run.py`. The key decision is that a non-symlink regular file under the resolved repository root must pass equivalent host data and metadata checks before its sandboxed checks may prove denial. On green, generic repositories no longer require `pyproject.toml`, while unavailable or unsafe proof rejects structural evaluation before any evidence, seed, or backend work.

## Table of Contents

- [Summary](#summary) — States the change, files, and green result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains the unsafe Python-specific probe assumption.
- [Input](#input) — Names the evaluator-session and runner contracts this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the two edited files.
- [Implementation](#implementation) — Defines safe probe selection and proof ordering.
- [Tests](#tests) — Covers generic selection, host proof, refusal, and live Seatbelt behavior.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion checks.
- [References](#references) — Links to the sandbox and Python APIs involved.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s safety and scope limits.
- [Deferred](#deferred) — Records the intentionally absent fallback proof.

## Why

`plan_tool/roadmap_structural_revision_run.py:_isolation_probes_pass` currently depends on `repo_root / "pyproject.toml"` and accepts `Path.is_file()` without proving the candidate’s ordinary host data and metadata access. That blocks generic consuming repositories without Python project metadata and can mistake a host-inaccessible file for a Seatbelt denial. The existing `tests/test_roadmap_structural_revision_run.py:test_structural_evaluator_rejection_stops_before_evidence_seed_or_backend` already proves that an unavailable evaluator stops the runner, but it does not prove safe generic sentinel selection or the host-versus-Seatbelt distinction.

## Input

- **Evaluator session:** `plan_tool/roadmap_structural_revision_run.py:StructuralEvaluatorSession` provides the isolated working directory and generated Seatbelt profile used by the probe and later evaluator call.

- **Admission boundary:** `plan_tool/roadmap_structural_revision_run.py:verified_structural_evaluator` resolves the repository and plans roots, creates the temporary evaluator root, and turns a failed probe into `StructuralEvaluatorError`.

- **Failure handling:** `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` maps `StructuralEvaluatorError` to the fact-free `evaluator-rejected` preflight result before loading evidence or invoking the backend.

- **Transport boundary:** `plan_tool/roadmap_structural_revision_run.py:_production_invoker` passes the admitted profile to `plan_tool/shell.py:structural_codex_invoke`; this step must preserve that profile-backed production transport.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_structural_revision_run.py` — Replace the fixed `pyproject.toml` assumption in `_isolation_probes_pass` with safe generic candidate selection and paired host/Sandbox proof checks.
  - `tests/test_roadmap_structural_revision_run.py` — Add focused generic-candidate, host-capability, fail-closed, and Seatbelt regression coverage.

## Implementation

- **Foundational rule:** Admit an evaluator session only when one repository-owned probe file proves both sides of the boundary: its ordinary host data and metadata reads succeed, then its equivalent Seatbelt-wrapped reads fail.

- **Select a generic safe candidate:** Update `plan_tool/roadmap_structural_revision_run.py:_isolation_probes_pass` so it does not require a Python-specific filename. Choose a deterministic repository-root candidate strategy that can work in a generic consuming repository, while leaving the exact enumeration method to implementation.

- **Require direct ownership:** Accept only a non-symlink regular file found under the resolved `repo_root`. Its resolved target must remain under that denied root. Reject links, outside targets, missing candidates, directories, and anything that cannot establish this direct ownership boundary.

- **Prove host capability first:** Run the same kind of data and metadata operations used for the denial proof against the selected candidate outside Seatbelt before the sandboxed data and metadata reads. The host operations must both return success; a nonzero result, launch error, or timeout makes the probe fail closed rather than being counted as a denial.

- **Keep proof target and ordering aligned:** Use the exact selected candidate for both host and Seatbelt checks. Perform the host data and metadata proof before the corresponding sandboxed denial checks, so a sandboxed nonzero result has one meaning: the profile denied a capability the host actually had.

- **Preserve the existing protections:** Keep `_seatbelt_profile`’s repository and plans-root read denials, its isolated-child write refusal, and the version and provider checks in `verified_structural_evaluator`. Do not add a profile allowance for the probe; the positive reads occur outside Seatbelt.

- **Keep evaluator failure fact-free and early:** Let `_isolation_probes_pass` report failure through the existing `verified_structural_evaluator` error path. When evaluator admission fails, `run_structural_revision` must reject before preflight evidence loading, seed invalidation, writer acquisition, or backend invocation.

- **Leave the transport unchanged:** `plan_tool/shell.py:structural_codex_invoke` already runs the real evaluator under the profile supplied by `_production_invoker`. This step changes admission proof only; it does not add an alternate evaluator transport or relax the runtime profile.

## Tests

### Tests for this step

- `test_isolation_probes_select_a_generic_owned_regular_file_without_pyproject` — Creates a repository fixture without `pyproject.toml` and proves the probe can select a safe repository-owned regular file.

- `test_isolation_probes_require_host_data_and_metadata_success_before_seatbelt_denial` — Records the probe commands and proves host `/bin/cat` and `/usr/bin/stat` success for the selected file precedes the corresponding sandboxed failures.

- `test_isolation_probes_reject_symlinked_or_outside_candidates` — Proves a link is never accepted as the sentinel, including a repository link whose target would escape the denied root.

- `test_isolation_probes_fail_closed_when_host_data_or_metadata_is_unavailable` — Parametrizes failed host data and metadata checks and proves neither can be reinterpreted as successful Seatbelt denial.

- `test_structural_seatbelt_profile_denies_protected_data_and_metadata_reads` — Extends the macOS-only live profile test to prove ordinary-host data and metadata access succeeds for its protected file while the same sandboxed operations, plus an isolated-root write, fail.

- **Green-before-done gate:** Every focused case in `tests/test_roadmap_structural_revision_run.py` passes before this step is complete.

## Acceptance criteria

- A generic repository without `pyproject.toml` can supply a repository-owned, non-symlink regular-file evaluator probe.

- `_isolation_probes_pass` returns failure when no candidate meets the direct-ownership and host-capability requirements.

- A candidate’s ordinary host data and metadata operations succeed before the Seatbelt denial checks run against that same candidate.

- A symlinked candidate, an outside target, or a host-inaccessible candidate cannot establish isolation proof.

- Seatbelt still denies repository data reads, repository metadata reads, and writes from the isolated evaluator root.

- When evaluator admission fails, `run_structural_revision` still returns `evaluator-rejected` before evidence, seed, writer, or backend work.

- `uv run pytest tests/test_roadmap_structural_revision_run.py -q` passes.

## References

- [sandbox-exec(1) macOS Manual Page](https://keith.github.io/xcode-man-pages/sandbox-exec.1.html) — Read the profile and command-execution rules used for the live denial probe.

- [Accessing Files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox) — Read the macOS file-access model behind the protected-root boundary.

- [Python 3.13 pathlib Documentation](https://docs.python.org/3.13/library/pathlib.html) — Read the regular-file, symlink, and path-resolution behavior needed for safe candidate selection.

- [Python 3.13 subprocess Documentation](https://docs.python.org/3.13/library/subprocess.html) — Read the bounded command, return-code, timeout, and output-discarding behavior used by the probes.

- [Python 3.13 tempfile Documentation](https://docs.python.org/3.13/library/tempfile.html) — Read the temporary-root cleanup contract preserved by `verified_structural_evaluator`.

## Applicable guardrails

- **Plan intent — generic-repository isolation:** Follow the plan’s `## Plan intent` by making admission work for generic repositories without weakening the evaluator boundary.

- **Step intent — verified macOS isolation:** Follow the plan’s step-2 intent by treating unavailable proof as rejection, not as permission to run without the data, metadata, or write protections.

- **Out of scope — bounded structural writer:** Follow the plan’s `## Out of scope` by leaving structural patch, publication, and writer-authority behavior unchanged.

- **Out of scope — narrow remediation:** Follow the plan’s `## Out of scope` by keeping this work in the evaluator admission path and its focused tests rather than adding a roadmap stage or a broader architecture change.

## Deferred

- Alternative isolation evidence for repositories without a safe repository-owned probe file — Follow the plan’s `## Deferred`; this step fails closed instead of introducing a fallback sandbox design.
