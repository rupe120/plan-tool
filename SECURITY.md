# Security policy

## Reporting a vulnerability

Report it privately through GitHub:
[report a vulnerability](https://github.com/rupe120/plan-tool/security/advisories/new).
Please do not open a public issue or pull request for it.

Include the output of `plan-tool --version`, what you ran, what happened, and the
impact you see. A minimal reproduction in a fresh repository helps most.

There is no fixed response time and no bounty. Reports are read in the order they
arrive, and you will hear back on the advisory as the work progresses.

## Supported versions

Only the latest release receives fixes. A fix ships as a new release; older
versions are not patched.

## How plan-tool runs code

plan-tool drives a coding assistant CLI to write and edit files. It starts that
CLI headless, with a mode that accepts edits without asking: Claude Code with
`--permission-mode acceptEdits`, Codex with a `workspace-write` sandbox, and
Cursor Agent with `--force --trust`. plan-tool is not a sandbox. Treat a plan, a
seed, a roadmap or a repository from an untrusted source as untrusted code, and
review what an assistant is asked to do before you run it.

## What to report

Examples of reports we want:

- Reading or writing files outside the repository being worked on.
- Secrets or credentials written into saved reports, run logs or telemetry.
- Argument or command injection through plan, seed or configuration content.

Not vulnerabilities: a backend CLI approving its own tool calls in the mode
above, or an assistant producing wrong or unsafe code. The assistant's own
security issues belong with its vendor.
