### Changed

- Running `plan-tool` with no arguments prints a short core path (skill
  install, plan, both audits, detail, run, reconcile) instead of the full
  usage block (BACKLOG #521). It is still a usage error: the text goes to stderr and the exit
  code stays 2. `plan-tool --help` still lists every subcommand.
- The installed skill now offers to set up a repository's project profile,
  asking for the intent and confirming the wording before it runs
  `plan-tool init`.
