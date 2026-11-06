# Install and update plan-tool

Keep a dedicated source clone for the installed CLI. An editable installation
reads code from that directory, so keep the clone at a stable path and use a
separate clone for development that should not immediately change your CLI.

## Install from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then clone the selected source:

```bash
git clone https://github.com/rupe120/plan-tool.git
cd plan-tool
uv tool install --editable .
plan-tool --version
uv tool list
```

If `plan-tool` is not on PATH, run `uv tool update-shell` and open a new shell,
or add the executable directory reported by uv to PATH.

If the source repository requires access, authenticate with the host before
cloning. Use the maintainer's announced source URL if its organization or location
changes.
Backend executables and their authentication are separate prerequisites; see
[Backends](../BACKENDS.md).

| Track | Use when | Selection |
| --- | --- | --- |
| Release tag | You want an explicitly selected release | Fetch tags and check out the announced `vX.Y.Z` tag before installing. Tags are available only after a maintainer publishes them. |
| `main` | You want reviewed changes as they merge | Keep the installation clone on `main`; update with a fast-forward pull. |

For a release tag, replace `vX.Y.Z` below with an actual announced tag:

```bash
git fetch origin --tags
git switch --detach vX.Y.Z
uv tool install --editable . --reinstall
```

Keep the clone after installation. Moving or deleting it breaks the editable
source reference; reinstall from its new location to repair that reference.
Preserve optional extras when reinstalling, for example
`uv tool install --editable '.[spell]' --reinstall`.

## Update the CLI and skill

Start with a clean installation clone. Finish or preserve local edits before
switching versions; a failed fast-forward requires inspection.

1. Select the next version. For `main`, run:

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

   For a tagged release, fetch and select the announced tag as above.
2. Refresh the installed tool environment:

   ```bash
   uv tool install --editable . --reinstall
   plan-tool --version
   uv tool list
   ```

   Editable code changes appear immediately, but dependency, entry-point and
   metadata changes need the environment refreshed. `uv sync --frozen` manages
   the clone's development `.venv`, a separate environment from `uv tool`.
   Tool dependencies resolve from package requirements; the repository lockfile
   does not pin the tool environment. See [uv tool environments](https://docs.astral.sh/uv/concepts/tools/).
3. Refresh copied assistant skills using the same integration and installation
   scope as the original install. For a user-level Codex installation:

   ```bash
   plan-tool install-skill --integration codex --user --force
   ```

   Project copies need refresh in each consuming repository; omit `--user` and
   repeat the original integration/root/copy options with `--force`. Review local
   skill edits before replacing them. Keep `SKILL.md` and `DIRECTIVES.md` together.
   Symlink installations follow their source clone; repair the links if it moves.
   See [skill installation](../../README.md#install-the-assistant-skill).
4. Restart or reload the assistant session so it reads the refreshed guidance.

To return to a prior release, select its tag, reinstall the tool environment and
refresh copied skills by the same procedure. Check the changelog before opening
persisted plans or runtime state with an older version; switching code does not
reverse data-format changes.

Maintainers preparing a shared Bitbucket/GitHub release use
[Releasing](../RELEASING.md#keep-bitbucket-and-github-synchronized).
