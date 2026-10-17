#!/usr/bin/env python3
"""Lab-only Optics observe step for GitHub Actions.

Replays a job's shell commands under ``vantio run`` in observe mode and writes
a local observation log. The process exits 0. Publish, attest, tag, release,
secret, and OIDC steps are recorded and not executed. On release workflows the
commands that produce published bytes are not executed, so those bytes stay
identical to a run without this step.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

OBSERVE_STEP = "Optics observe (Lab-only)"
UPLOAD_STEP = "Upload Optics observation log (Lab-only)"
SCHEMA = "vantio.optics_observe_ci.v1"
PUBLIC_PIN_PREFIX = "e0b19d55"

RELEASE_WORKFLOWS = frozenset(
    {
        "npm-publish.yml",
        "pypi-publish.yml",
        "mcp-registry-publish.yml",
        "enterprise-slsa-provenance.yml",
    }
)

EXPR = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")
SENSITIVE_KEY = re.compile(r"(TOKEN|SECRET|PASSWORD|CREDENTIAL|PRIVATE_KEY|API_KEY)", re.IGNORECASE)
JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
DENY = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"secrets\.",
        r"github\.token",
        r"\bGH_TOKEN\b",
        r"\bGITHUB_TOKEN\b",
        r"\bNPM_TOKEN\b",
        r"\bNODE_AUTH_TOKEN\b",
        r"\bPYPI_TOKEN\b",
        r"\bTWINE_[A-Z0-9_]*",
        r"\bPASSWORD\b",
        r"npm publish",
        r"pnpm publish",
        r"yarn publish",
        r"--publish\b",
        r"mcp-publisher publish",
        r"mcp-publisher login",
        r"github-oidc",
        r"\bgh release\b",
        r"\bgit tag\b",
        r"docker push",
        r"\btwine\b",
        r"attest",
        r"gh-action-pypi-publish",
        r"fetch_custody_release\.py",
        r"id-token",
        r"ACTIONS_ID_TOKEN",
        r"GITHUB_STEP_SUMMARY",
    )
)

NODE_WRAPPER = """\
const { spawnSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const file = process.env.OPTICS_OBSERVE_CURRENT_SCRIPT;
if (!file) process.exit(1);
const script = readFileSync(file, "utf8");
const env = Object.assign({}, process.env);
delete env.OPTICS_OBSERVE_CURRENT_SCRIPT;
const child = spawnSync("bash", ["-lc", script], { stdio: "inherit", env });
if (child.error) process.exit(1);
process.exit(child.status === null ? 1 : child.status);
"""

SUB_KEYS = {
    "inputs.package": "OPTICS_OBSERVE_INPUT_PACKAGE",
    "inputs.version": "OPTICS_OBSERVE_INPUT_VERSION",
    "inputs.source_commit": "OPTICS_OBSERVE_INPUT_COMMIT",
    "inputs.artifact_sha256": "OPTICS_OBSERVE_INPUT_SHA256",
    "matrix.python-version": "OPTICS_OBSERVE_PYTHON_VERSION",
    "github.sha": "GITHUB_SHA",
    "github.actor": "GITHUB_ACTOR",
    "github.workspace": "GITHUB_WORKSPACE",
    "runner.temp": "RUNNER_TEMP",
    "github.ref": "GITHUB_REF",
    "github.repository": "GITHUB_REPOSITORY",
    "github.event_name": "GITHUB_EVENT_NAME",
    "github.workflow_ref": "GITHUB_WORKFLOW_REF",
}


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def substitutions(environ: dict[str, str]) -> dict[str, str]:
    found = {}
    for expr, key in SUB_KEYS.items():
        if key in environ and environ[key] is not None:
            found[expr] = environ[key]
    return found


def apply_subs(text: str | None, subs: dict[str, str]) -> str | None:
    if text is None:
        return None

    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key == "github.token" or key.startswith("secrets.") or key.startswith("github.token"):
            return match.group(0)
        if key in subs:
            return subs[key]
        return match.group(0)

    return EXPR.sub(repl, text)


def denied(script: str) -> bool:
    return any(pattern.search(script) for pattern in DENY)


def env_is_sensitive(env: dict[str, str]) -> bool:
    for key, value in env.items():
        if SENSITIVE_KEY.search(key):
            return True
        if "secrets." in value or "github.token" in value:
            return True
    return False


def release_allowed(script: str) -> bool:
    """Commands that do not write published bytes and do not publish."""
    if "promote_npm.mjs" in script and "--gate" in script and "--publish" not in script:
        return True
    if (
        "stage_sealed_pypi.py" in script
        and "--reject-existing-version" in script
        and "--source" not in script
        and "upload" not in script
    ):
        return True
    if script.strip() == "mcp-publisher validate":
        return True
    if "package is not on the MCP allowlist" in script and "mcp-publisher" not in script and "publish" not in script:
        return True
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if lines and all(line.startswith("set -") or line.startswith("test ") for line in lines):
        return True
    return False


def effective_policy(requested: str | None, workflow_name: str) -> str:
    if Path(workflow_name).name in RELEASE_WORKFLOWS:
        return "release"
    if requested == "release":
        return "release"
    return "replay"


def dedent_block(raw: list[str]) -> str:
    indents = [len(line) - len(line.lstrip(" ")) for line in raw if line.strip()]
    cut = min(indents) if indents else 0
    parts = []
    for line in raw:
        if line.strip() == "":
            parts.append("")
        else:
            parts.append(line[cut:])
    return "\n".join(parts).rstrip("\n")


def parse_step(chunk: list[str]) -> dict:
    name = None
    workdir = None
    shell = None
    uses = None
    env: dict[str, str] = {}
    run = None
    index = 0
    while index < len(chunk):
        line = chunk[index]
        named = re.match(r"^      - name:\s*(.*)$", line) or re.match(r"^        name:\s*(.*)$", line)
        if named and name is None:
            name = unquote(named.group(1).strip())
            index += 1
            continue
        used = re.match(r"^        uses:\s*(\S+)", line)
        if used:
            uses = used.group(1)
            index += 1
            continue
        directory = re.match(r"^        working-directory:\s*(.*)$", line)
        if directory:
            workdir = unquote(directory.group(1).strip())
            index += 1
            continue
        shell_match = re.match(r"^        shell:\s*(\S+)", line)
        if shell_match:
            shell = shell_match.group(1)
            index += 1
            continue
        if re.match(r"^        env:\s*$", line):
            index += 1
            while index < len(chunk):
                pair = re.match(r"^          ([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", chunk[index])
                if not pair:
                    break
                env[pair.group(1)] = unquote(pair.group(2).strip())
                index += 1
            continue
        if re.match(r"^        run:\s*\|\s*$", line):
            index += 1
            raw = []
            while index < len(chunk):
                content = chunk[index]
                if content.strip() == "":
                    raw.append("")
                    index += 1
                    continue
                if content.startswith("          "):
                    raw.append(content)
                    index += 1
                    continue
                break
            run = dedent_block(raw)
            continue
        inline = re.match(r"^        run:\s*(.+)$", line)
        if inline:
            run = unquote(inline.group(1).strip())
            index += 1
            continue
        index += 1
    return {
        "name": name,
        "run": run,
        "working_directory": workdir,
        "shell": shell,
        "uses": uses,
        "env": env,
    }


def parse_job_steps(body: list[str]) -> list[dict]:
    start = None
    for index, line in enumerate(body):
        if line == "    steps:":
            start = index + 1
            break
    if start is None:
        return []
    chunks: list[list[str]] = []
    current: list[str] | None = None
    for line in body[start:]:
        if line.startswith("      - "):
            if current is not None:
                chunks.append(current)
            current = [line]
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        chunks.append(current)
    return [parse_step(chunk) for chunk in chunks]


def parse_jobs(text: str) -> dict[str, list[dict]]:
    lines = text.splitlines()
    try:
        start = lines.index("jobs:")
    except ValueError:
        return {}
    jobs: dict[str, list[dict]] = {}
    index = start + 1
    while index < len(lines):
        line = lines[index]
        if line and not line.startswith(" "):
            break
        matched = JOB_KEY.match(line)
        if not matched:
            index += 1
            continue
        job_id = matched.group(1)
        index += 1
        body: list[str] = []
        while index < len(lines):
            nxt = lines[index]
            if JOB_KEY.match(nxt) or (nxt and not nxt.startswith(" ")):
                break
            body.append(nxt)
            index += 1
        jobs[job_id] = parse_job_steps(body)
    return jobs


def is_observer(step: dict) -> bool:
    name = step.get("name") or ""
    script = step.get("run") or ""
    return name.startswith(OBSERVE_STEP) or name.startswith(UPLOAD_STEP) or "optics_observe.py" in script


def has_unexpanded(script: str | None, workdir: str | None, env: dict[str, str]) -> bool:
    parts = [script or "", workdir or "", *env.values()]
    return any("${{" in part for part in parts)


def classify(step: dict, workflow_name: str, policy: str, subs: dict[str, str]) -> dict:
    policy = effective_policy(policy, workflow_name)
    if step.get("uses") and not step.get("run"):
        uses = step["uses"]
        reason = "uses_step"
        if re.search(r"attest|gh-action-pypi-publish|mcp-publisher", uses, re.IGNORECASE):
            reason = "publisher_action_not_replayed"
        if (step.get("name") or "").startswith(UPLOAD_STEP):
            reason = "observer_upload"
        return {
            "name": step.get("name"),
            "action": "skip",
            "reason": reason,
            "script": None,
            "working_directory": None,
            "env": {},
            "uses": uses,
        }
    if is_observer(step):
        return _skipped(step, "observer_step")
    if env_is_sensitive(step.get("env") or {}):
        return _skipped(step, "secret_or_token_env")
    script = apply_subs(step.get("run"), subs) or ""
    workdir = apply_subs(step.get("working_directory"), subs)
    env = {key: apply_subs(value, subs) or "" for key, value in (step.get("env") or {}).items()}
    shell = step.get("shell")
    if shell and not shell.startswith("bash"):
        return _skipped(step, "shell_not_bash", script, workdir, env)
    if denied(script):
        return _skipped(step, "denied_command", script, workdir, env)
    if has_unexpanded(script, workdir, env):
        return _skipped(step, "unexpanded_expression", script, workdir, env)
    if policy == "release" and not release_allowed(script):
        return _skipped(step, "release_bytes_not_replayed", script, workdir, env)
    if not script.strip():
        return _skipped(step, "empty_command", script, workdir, env)
    return {
        "name": step.get("name"),
        "action": "run",
        "reason": "observe",
        "script": script,
        "working_directory": workdir,
        "env": env,
        "uses": step.get("uses"),
    }


def _skipped(
    step: dict,
    reason: str,
    script: str | None = None,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    return {
        "name": step.get("name"),
        "action": "skip",
        "reason": reason,
        "script": script if script is not None else step.get("run"),
        "working_directory": workdir if workdir is not None else step.get("working_directory"),
        "env": env if env is not None else {},
        "uses": step.get("uses"),
    }


def plan_job(text: str, workflow_name: str, job_id: str, policy: str, subs: dict[str, str]) -> list[dict]:
    jobs = parse_jobs(text)
    if job_id not in jobs:
        return []
    return [classify(step, workflow_name, policy, subs) for step in jobs[job_id]]


def secret_values(environ: dict[str, str]) -> list[str]:
    found = []
    for key, value in environ.items():
        if value and len(value) >= 8 and SENSITIVE_KEY.search(key):
            found.append(value)
    return found


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    return text


def child_environment(base: dict[str, str], step_env: dict[str, str], home: Path, cli: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in base.items():
        if SENSITIVE_KEY.search(key):
            continue
        env[key] = value
    for key, value in step_env.items():
        if SENSITIVE_KEY.search(key) or "secrets." in value or "github.token" in value:
            continue
        env[key] = value
    env["VANTIO_HOME"] = str(home)
    env["VANTIO_MCP_MODE"] = "observe"
    env["VANTIO_MCP_INJECTION"] = "log"
    env["VANTIO_MCP_RUG_PULL"] = "log"
    env.pop("VANTIO_API_KEY", None)
    wrap = cli.parent / "python-wrap"
    if wrap.is_dir():
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(wrap) + (os.pathsep + current if current else "")
    return env


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def locate_cli(root: Path, temp: Path, environ: dict[str, str]) -> Path | None:
    override = environ.get("OPTICS_OBSERVE_CLI")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None
    direct = root / "packages" / "vantio-cli" / "bin" / "vantio.js"
    if direct.is_file():
        return direct
    dest = temp / "optics-cli-extract"
    # A sparse checkout must not grow a packages tree inside the workspace.
    if inside(dest, root):
        return None
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "HEAD", "packages/vantio-cli"],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if archive.returncode != 0 or not archive.stdout:
        return None
    extracted = subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        input=archive.stdout,
        check=False,
        capture_output=True,
    )
    if extracted.returncode != 0:
        return None
    cli = dest / "packages" / "vantio-cli" / "bin" / "vantio.js"
    return cli if cli.is_file() else None


def resolve_cwd(root: Path, workdir: str | None) -> Path | None:
    if not workdir:
        return root
    path = Path(workdir)
    if not path.is_absolute():
        path = root / path
    return path if path.is_dir() else None


def run_process(argv: list[str], env: dict[str, str], cwd: Path, timeout: int) -> tuple[int, bool]:
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, start_new_session=True)
    try:
        return proc.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 124, True


def default_runner(item: dict, ctx: dict) -> tuple[int, bool]:
    script_path = ctx["script_dir"] / f"{ctx['index']}.sh"
    script_path.write_text(item["script"], encoding="utf-8")
    env = child_environment(ctx["base_env"], item["env"], ctx["home"], ctx["cli"])
    env["OPTICS_OBSERVE_CURRENT_SCRIPT"] = str(script_path)
    argv = [ctx["node"], str(ctx["cli"]), "run", "node", "-e", NODE_WRAPPER]
    if "--mcp-enforce" in argv:
        return 1, False
    return run_process(argv, env, ctx["cwd"], ctx["timeout"])


def public_command(item: dict, exit_code: int | None = None, timed_out: bool = False) -> dict:
    record = {
        "name": item.get("name"),
        "action": "ran" if item.get("action") == "run" and exit_code is not None else "skipped",
        "reason": item.get("reason"),
        "timed_out": timed_out,
    }
    if exit_code is not None and item.get("action") == "run":
        record["exit_code"] = exit_code
        record["action"] = "ran"
    if item.get("uses"):
        record["uses"] = item["uses"]
    return record


def execute_plan(items: list[dict], ctx: dict, runner) -> list[dict]:
    results = []
    for index, item in enumerate(items):
        if item["action"] != "run":
            results.append(public_command(item))
            continue
        cwd = resolve_cwd(ctx["root"], item.get("working_directory"))
        if cwd is None:
            skipped = dict(item)
            skipped["action"] = "skip"
            skipped["reason"] = "workdir_missing"
            results.append(public_command(skipped))
            continue
        if ctx.get("cli") is None:
            skipped = dict(item)
            skipped["action"] = "skip"
            skipped["reason"] = "cli_unavailable"
            results.append(public_command(skipped))
            continue
        if shutil.which(ctx["node"]) is None and not Path(ctx["node"]).is_file():
            skipped = dict(item)
            skipped["action"] = "skip"
            skipped["reason"] = "node_unavailable"
            results.append(public_command(skipped))
            continue
        step_ctx = dict(ctx)
        step_ctx["cwd"] = cwd
        step_ctx["index"] = index
        try:
            code, timed_out = runner(item, step_ctx)
        except AssertionError:
            raise
        except Exception:
            code, timed_out = 1, False
        results.append(public_command(item, code, timed_out))
        print(
            f"Optics observe Lab-only step={item.get('name')} action=ran exit={code} timed_out={timed_out}",
            flush=True,
        )
    return results


def copy_logs(home: Path, out: Path, secrets: list[str]) -> int:
    copied = 0
    runs = home / "runs"
    target = out / "runs"
    if runs.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(runs.glob("*.json")):
            text = path.read_text(encoding="utf-8", errors="replace")
            (target / path.name).write_text(redact(text, secrets), encoding="utf-8")
            copied += 1
    mcp = home / "mcp-observations.jsonl"
    if mcp.is_file():
        text = mcp.read_text(encoding="utf-8", errors="replace")
        (out / "mcp-observations.jsonl").write_text(redact(text, secrets), encoding="utf-8")
        copied += 1
    return copied


def manifest_template(workflow: str, job: str, policy: str, status: str) -> dict:
    return {
        "schema": SCHEMA,
        "evidence_label": "Lab-only",
        "mode": "observe",
        "enforcement": "not_enabled",
        "mcp_mode": "observe",
        "workflow": workflow,
        "job": job,
        "policy": policy,
        "status": status,
        "commands": [],
        "run_logs": 0,
    }


def write_manifest(out: Path, body: dict, secrets: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    (out / "manifest.json").write_text(redact(text, secrets), encoding="utf-8")


def output_dir(environ: dict[str, str]) -> Path:
    if environ.get("OPTICS_OBSERVE_OUT"):
        return Path(environ["OPTICS_OBSERVE_OUT"])
    temp = Path(environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    return temp / "optics-observe-artifact"


def command_timeout(environ: dict[str, str], policy: str) -> int:
    raw = environ.get("OPTICS_OBSERVE_COMMAND_TIMEOUT")
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return 120 if policy == "release" else 900


def run_observation(environ: dict[str, str], runner=None) -> dict:
    workflow_value = environ.get("OPTICS_OBSERVE_WORKFLOW", "")
    job = environ.get("OPTICS_OBSERVE_JOB", "")
    root = Path(environ.get("OPTICS_OBSERVE_ROOT") or environ.get("GITHUB_WORKSPACE") or os.getcwd())
    policy = effective_policy(environ.get("OPTICS_OBSERVE_POLICY"), workflow_value)
    out = output_dir(environ)
    secrets = secret_values(environ)
    body = manifest_template(workflow_value, job, policy, "ok")
    try:
        workflow = Path(workflow_value)
        if not workflow.is_absolute():
            workflow = root / workflow
        if not workflow.is_file() or not job:
            body["status"] = "workflow_unreadable"
            write_manifest(out, body, secrets)
            return body
        text = workflow.read_text(encoding="utf-8")
        jobs = parse_jobs(text)
        if job not in jobs:
            body["status"] = "job_missing"
            write_manifest(out, body, secrets)
            return body
        items = plan_job(text, workflow.name, job, policy, substitutions(environ))
        temp = Path(environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        cli = locate_cli(root, temp, environ)
        home = temp / "optics-observe-home"
        if home.exists():
            shutil.rmtree(home)
        home.mkdir(parents=True, exist_ok=True)
        script_dir = temp / "optics-observe-scripts"
        if script_dir.exists():
            shutil.rmtree(script_dir)
        script_dir.mkdir(parents=True, exist_ok=True)
        node = environ.get("OPTICS_OBSERVE_NODE") or "node"
        ctx = {
            "root": root,
            "cli": cli,
            "node": node,
            "home": home,
            "timeout": command_timeout(environ, policy),
            "script_dir": script_dir,
            "base_env": {key: value for key, value in environ.items()},
        }
        chosen = runner or default_runner
        body["commands"] = execute_plan(items, ctx, chosen)
        body["run_logs"] = copy_logs(home, out, secrets)
        for command in body["commands"]:
            if command["action"] == "skipped":
                print(
                    f"Optics observe Lab-only step={command.get('name')} action=skipped reason={command.get('reason')}",
                    flush=True,
                )
        write_manifest(out, body, secrets)
        # Re-redact after the manifest write in case a log was copied with a secret.
        manifest_path = out / "manifest.json"
        manifest_path.write_text(redact(manifest_path.read_text(encoding="utf-8"), secrets), encoding="utf-8")
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except AssertionError:
        raise
    except Exception:
        body["status"] = "observe_error"
        body["commands"] = []
        write_manifest(out, body, secrets)
        return body


def main() -> int:
    try:
        run_observation(dict(os.environ))
    except Exception:
        try:
            out = output_dir(dict(os.environ))
            write_manifest(
                out,
                manifest_template(
                    os.environ.get("OPTICS_OBSERVE_WORKFLOW", ""),
                    os.environ.get("OPTICS_OBSERVE_JOB", ""),
                    effective_policy(os.environ.get("OPTICS_OBSERVE_POLICY"), os.environ.get("OPTICS_OBSERVE_WORKFLOW", "")),
                    "observe_error",
                ),
                secret_values(dict(os.environ)),
            )
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
