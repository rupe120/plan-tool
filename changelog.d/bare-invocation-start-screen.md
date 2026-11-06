### Changed

- Running `plan-tool` with no arguments prints a short core path (skill
  install, plan, both audits, detail, run, reconcile) before its usage error,
  instead of the full usage block (BACKLOG #521). It still prints to stderr
  and exits 2. `plan-tool --help` still lists every subcommand.
- The installed skill now offers to set up a repository's project profile,
  asking for the intent and confirming the wording before it runs
  `plan-tool init`.
