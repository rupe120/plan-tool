# Repository assistant setup

Tracked skills describe reusable procedures. Organization targets belong in
ignored `.claude/local/project-context.json`, not in a skill or shared directive.
Copy `.claude/project-context.example.json` there and fill in the local values.
Never place credentials in this file; use the configured tools' authentication.

| Setting | Consumer |
| --- | --- |
| `jira.site_url`, `project_key`, `project_id`, `board_id`, `board_url` | The Jira-ticket skill reads these before choosing a target; verify them with the configured Atlassian MCP server. |
| `bitbucket.workspace`, `repository`, `api_url`, `clone_url` | Internal checkout/setup reference. PR operations still verify their target against the actual Git remote. |
| `integration_consumer.checkout` | Local source root corresponding to `<integration-consumer-root>` in retained evidence and source references. |

This is assistant-readable local context, not a new plan-tool runtime
configuration contract. It does not implement BACKLOG #509 or automatically
configure a connector. Missing target details require clarification; tracked
example ticket keys do not select a tenant or project.

Contributor identity mappings may live in ignored `.claude/local/mailmap`.
To use that file in this checkout, set Git's local configuration:

```bash
git config --local mailmap.file .claude/local/mailmap
```

A fresh clone has neither private settings nor identity mappings. Populate only
the targets needed on that workstation. Changes to tracked files do not remove
organization data from existing commits; the public-history boundary remains a
separate release decision.
