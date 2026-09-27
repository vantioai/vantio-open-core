# Upgrade, rollback, and uninstall

## Versions you can install today

| Package | Install | Published | In this git tree |
| --- | --- | --- | --- |
| CLI | `npm install -g @vantio/cli@0.3.24` | 0.3.24 | 0.3.24 frozen |
| Python | `pip install 'vantio-agent-sdk==3.0.14'` | 3.0.14 | 3.1.0 unpublished |

Do not bump package versions as part of reading this manual. This manual does not publish anything.

Unpublished Python 3.0.15 exists only in git history. It is not the PyPI package. Unpublished 3.1.0 is the version string in this commit's `pyproject.toml`. Behavior differences: [PYTHON-GUIDE.md](PYTHON-GUIDE.md).

## From Python v2

v3.0.0 removed `VantioSession` and `VANTIO_PROXY_ENDPOINT`. Observe runs inside the process. There is no proxy endpoint to configure.

```python
# Example status: illustrative
from vantio import shield

@shield
async def run_agent():
    ...
```

Or keep the script unchanged and start it with `vantio run python agent.py` after installing 3.0.14. Confirm a supported call appears in `vantio tail` before you treat the process as covered.

v2 files, if you still have them, are not migrated. The CLI accepts JSON objects that carry `vantio_run_log` `"1"` and does not convert older shapes.

## From Python 3.0.x to a future 3.1.0

When 3.1.0 is published, read its changelog before you upgrade. Until then, production installs stay on 3.0.14. Expect these storage differences after a real 3.1.0 release, based on unpublished source, not on a promise that the published diff will be identical:

- `ok` follows HTTP status (false for 400–599)
- Extra outcome fields and `schema_status` on the Python run file
- Telemetry becomes opt-in (`VANTIO_TELEMETRY=1`), matching the CLI
- Socket connect duration is measured around the real connect

CLI 0.3.24 will still display application outcome from the HTTP status and will still ignore `ok`. You do not need a CLI upgrade to read a 3.1.0 file's status code. You do need to avoid assuming 3.1.0 fields exist on a 3.0.14 file.

The CLI is frozen at 0.3.24. Customer sentences such as "Provider rate-limited the request" are in unpublished Python source. They are not CLI 0.3.24 labels.

## Mixed files in one directory

Node and Python files share `~/.vantio/runs` and share `schema_version` 2. Their envelopes differ (pid, `by_host`, `workflow`, provider label). `vantio diff` uses `summary.by_host` when it is present and otherwise sums `calls`. A Python 3.0.14 file takes the second path.

There is no negotiation and no refusal of a newer file. Restoring an older CLI keeps best-effort parsing.

## Rollback

```bash
# Example status: illustrative
npm install -g @vantio/cli@0.3.24
pip install 'vantio-agent-sdk==3.0.14'
```

Rollback does not rewrite run files. Old and new files remain side by side until you delete them. There is no downgrade migration.

## Retention

No command prunes by age or size. Files remain until you delete them. Disk use is unbounded. That is the current behavior. It is not a retention policy you can configure.

## Cleanup

| Action | Effect |
| --- | --- |
| `vantio logout` | Deletes `~/.vantio/config.json` if it exists. Does not read the file. Does not delete `runs/`. Omitted from help. |
| Delete `~/.vantio/runs/*.json` | Removes local run logs you choose. There is no dry-run and no deletion manifest. |
| Delete `~/.vantio/telemetry-id` | The next opted-in ping creates a new random id. |
| Delete a proof HTML/Markdown file you wrote | Removes that export only. |

There is no command to delete one run by trace id. Remove the matching file under `runs/`. Remember prefix collisions if you delete by a short prefix. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Uninstall

```bash
# Example status: illustrative
npm uninstall -g @vantio/cli
pip uninstall vantio-agent-sdk
```

Uninstalling the packages leaves `~/.vantio` in place, including run logs and `telemetry-id`. Remove that directory yourself when you want the local data gone.

The Node SDK and the MCP package are separate:

```bash
# Example status: illustrative
npm uninstall @vantio/agent-sdk
npm uninstall -g @vantio/optics-mcp
```

Uninstall does not unenroll a Phantom Engine host. This manual does not cover that product.

## Accounts

Free Optics 0.3.24 does not use `vantio login`. Older docs that tell you to log in before `vantio run` are stale. A leftover config file is removed with `vantio logout` or by deleting the file.
