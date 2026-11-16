### Added

- `create` prints `create-refused: reason=<token>` on its own stderr line when it refuses a seed or inline description before the slug resolves, so a driver can tell why no run log exists. The tokens are a closed set, listed in `DATA_CONTRACT.md` § "Pre-slug `create` refusals"; the exit code stays `2` (BACKLOG #502).
