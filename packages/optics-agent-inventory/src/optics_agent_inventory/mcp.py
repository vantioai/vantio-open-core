"""MCP structure. Descriptions, env values, headers, and positional args are dropped."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from optics_agent_inventory.catalog import catalog_in_scope, guess_provider, is_flag, is_mcp_server_name

MAX_BYTES = 65536
_RELATIVE = ("mcp.json", ".mcp.json", ".cursor/mcp.json", ".vscode/mcp.json")


def relative_paths() -> tuple[str, ...]:
    return _RELATIVE


def parse_mcp(blob: bytes, extra: tuple[str, ...], basis: str) -> list[dict[str, object]]:
    if len(blob) > MAX_BYTES:
        raise ValueError("oversize")
    try:
        parsed = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as err:
        raise ValueError("json") from err
    if not isinstance(parsed, dict):
        return []
    servers = parsed.get("mcpServers")
    if not isinstance(servers, dict):
        return []
    rows: list[dict[str, object]] = []
    for name, body in servers.items():
        if not isinstance(name, str) or not is_mcp_server_name(name) or not isinstance(body, dict):
            continue
        command = body.get("command")
        command_base = ""
        if isinstance(command, str) and command and "/" not in command and "\\" not in command and " " not in command:
            command_base = command
        elif isinstance(command, str) and command:
            command_base = command.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if " " in command_base or not command_base:
                command_base = ""
        flags: list[str] = []
        args = body.get("args")
        if isinstance(args, list):
            for arg in args:
                if isinstance(arg, str) and is_flag(arg):
                    flags.append(arg)
        url_host = None
        url_port = None
        url = body.get("url")
        if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
            parsed_url = urlparse(url)
            host = (parsed_url.hostname or "").lower()
            if host and catalog_in_scope(host, parsed_url.port, extra):
                url_host = host
                url_port = parsed_url.port
        row: dict[str, object] = {
            "name": name,
            "command_basename": command_base,
            "args": flags,
            "basis": basis,
        }
        if url_host:
            row["url_host"] = url_host
            row["url_port"] = url_port
            row["provider"] = guess_provider(url_host, url_port)
        rows.append(row)
    return rows
