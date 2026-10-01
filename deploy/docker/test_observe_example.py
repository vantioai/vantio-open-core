"""Contract for the Optics observe Docker example.

The example must pin an exact CLI version, keep secrets out of the build
context, and start Node under ``vantio run`` so observation actually attaches.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

DOCKER = Path(__file__).resolve().parent
DOCKERFILE = DOCKER / "Dockerfile.observe"
COMPOSE = DOCKER / "compose.observe.yml"
IGNORE = DOCKER / ".dockerignore"
AGENT = DOCKER / "agent.js"

_PIN = re.compile(r"@vantio/cli@([^\s\"']+)")
_EXACT = re.compile(r"^\d+\.\d+\.\d+$")
_ENTRYPOINT = re.compile(r"^ENTRYPOINT\s+(\[.*\])\s*$", re.M)
_CMD = re.compile(r"^CMD\s+(\[.*\])\s*$", re.M)
_SECRET_LINES = (
    "**/.env",
    "**/.env.*",
    "**/.git",
    "**/.git/**",
    "**/.ssh",
    "**/.ssh/**",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa",
    "**/*credentials*",
    "**/secrets",
    "**/secrets/**",
    "**/.npmrc",
)


class ObserveExampleTests(unittest.TestCase):
    def test_cli_pin_is_exact_and_matches_the_tree(self) -> None:
        cli = (DOCKER.parents[1] / "packages" / "vantio-cli" / "package.json").read_text(encoding="utf-8")
        version = re.search(r'"version":\s*"([^"]+)"', cli)
        self.assertIsNotNone(version)
        expected = version.group(1)
        pins = []
        for path in (DOCKERFILE, COMPOSE):
            for match in _PIN.finditer(path.read_text(encoding="utf-8")):
                pins.append((path.name, match.group(1)))
        self.assertTrue(pins, "the observe example does not pin @vantio/cli")
        for name, pin in pins:
            self.assertNotIn("^", pin, name)
            self.assertNotIn("~", pin, name)
            self.assertIsNotNone(_EXACT.fullmatch(pin), f"{name} pin {pin} is not exact")
            self.assertEqual(pin, expected, name)
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        self.assertNotIn("@vantio/cli@^", dockerfile)
        self.assertNotIn("@vantio/cli@~", dockerfile)
        self.assertNotRegex(dockerfile, r"npm install -g @vantio/cli(\s|$)")

    def test_default_command_runs_node_under_vantio_run(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")
        entry = _ENTRYPOINT.search(text)
        cmd = _CMD.search(text)
        self.assertIsNotNone(entry)
        self.assertIsNotNone(cmd)
        self.assertEqual(entry.group(1), '["vantio", "run", "node"]')
        self.assertNotIn('"npm"', cmd.group(1))
        self.assertIn("agent.js", cmd.group(1))
        self.assertNotIn("VANTIO_OBSERVE", text)
        agent = AGENT.read_text(encoding="utf-8")
        self.assertNotIn("fetch(", agent)
        self.assertNotIn("http.request", agent)
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("VANTIO_HOOKS=0", compose)
        self.assertNotIn("|| true", compose)

    def test_build_context_is_strict_and_excludes_secrets(self) -> None:
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        self.assertNotIn("COPY .", dockerfile)
        self.assertIn("COPY package.json agent.js", dockerfile)
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("../..", compose)
        self.assertIn("context: .", compose)
        self.assertTrue(IGNORE.is_file(), ".dockerignore is missing")
        ignored = IGNORE.read_text(encoding="utf-8")
        for line in _SECRET_LINES:
            self.assertIn(line, ignored.splitlines(), line)
        self.assertIn("\n*\n", f"\n{ignored}")
        for name in (".env", ".env.local", "id_rsa", "secrets/token", ".git/config", ".ssh/id_rsa", "keys/app.pem"):
            self.assertTrue(_docker_ignored(ignored, name), name)
        self.assertFalse(_docker_ignored(ignored, "agent.js"))
        self.assertFalse(_docker_ignored(ignored, "package.json"))
        self.assertFalse(_docker_ignored(ignored, "Dockerfile.observe"))


def _docker_ignored(text: str, relpath: str) -> bool:
    """Last-match dockerignore check for the patterns this example uses."""
    ignored = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = line[1:] if negate else line
        if _docker_match(pattern, relpath):
            ignored = not negate
    return ignored


def _docker_match(pattern: str, relpath: str) -> bool:
    if pattern == "*":
        return "/" not in relpath
    regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?")
    regex = regex.replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    if pattern.startswith("**/"):
        return re.fullmatch(regex, relpath) is not None
    return re.fullmatch(regex, relpath) is not None or re.fullmatch(regex, relpath.split("/")[-1]) is not None


if __name__ == "__main__":
    unittest.main()
