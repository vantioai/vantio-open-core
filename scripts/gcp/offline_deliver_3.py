def _run_guest(project: str, name: str, command: str, reason: str) -> subprocess.CompletedProcess[str]:
    completed = _ssh(project, name, command)
    if completed.returncode != 0:
        detail = redact((completed.stdout or "") + (completed.stderr or ""))
        print(detail[-4000:], file=sys.stderr)
        raise SystemExit(reason)
    return completed


def _wait_until_running(project: str, name: str) -> None:
    deadline = time.time() + SSH_WAIT_SECONDS
    status = ""
    while time.time() < deadline:
        described = _run(
            [
                "gcloud",
                "compute",
                "instances",
                "describe",
                name,
                f"--project={project}",
                f"--zone={ZONE}",
                "--format=value(status)",
            ]
        )
        status = (described.stdout or "").strip()
        if described.returncode == 0 and status == "RUNNING":
            break
        time.sleep(5)
    if status != "RUNNING":
        raise SystemExit("instance_status")
    _wait_ssh(project, name, SSH_WAIT_SECONDS)


def plumb_guest(env: Mapping[str, str]) -> int:
    """Copy the bundle over IAP and re-check the digest. Does not run batteries."""
    _enabled(env)
    if batteries_requested(env):
        raise SystemExit("batteries")
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    _gate_ok(env)
    seal = expected_seal(env)
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    evidence = _evidence_dir(env)
    bundle = Path(env.get("W3_BUNDLE_DIR", ""))
    guest = Path(env.get("GUEST_SCRIPT", ""))
    checked = assert_bundle_dir(bundle, seal)
    if checked["contract_sha256"] != env.get("EXPECTED_CONTRACT_SHA256", "").strip():
        raise SystemExit("contract_sha")
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "gcp-guest-payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir(parents=True)
    try:
        shutil.copy2(bundle / "seal.oci.tar", payload_dir / "seal.oci.tar")
        shutil.copy2(bundle / "contract.tar", payload_dir / "contract.tar")
        script_dest = payload_dir / "enterprise-rows.sh"
        shutil.copy2(guest, script_dest)
        script_dest.chmod(0o755)
        _wait_until_running(project, name)
        made = _ssh(project, name, f"sudo mkdir -p /var/lib/vantio-lab && sudo rm -rf {GUEST_DIR} && sudo mkdir -p {GUEST_DIR} && sudo chown -R $(id -u):$(id -g) /var/lib/vantio-lab {GUEST_DIR} && chmod 755 /var/lib/vantio-lab {GUEST_DIR}")
        if made.returncode != 0:
            raise SystemExit("ssh")
        _scp_to(
            project,
            name,
            [payload_dir / "seal.oci.tar", payload_dir / "contract.tar", script_dest],
        )
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        ran = _ssh(project, name, guest_command(seal, "plumb"))
        if ran.returncode != 0:
            print(redact((ran.stdout or "") + (ran.stderr or ""))[-4000:], file=sys.stderr)
            raise SystemExit("plumb")
        local = evidence / "gcp-plumb.json"
        if not _scp_from(project, name, "/tmp/gcp-plumb.json", local):
            raise SystemExit("plumb")
        body = _load_json_file(local)
        if not isinstance(body, dict) or body.get("seal_sha256") != seal or body.get("batteries") is not False:
            raise SystemExit("seal")
        result = {
            "batteries": False,
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "mode": "plumb",
            "network": NETWORK,
            "public_ip": False,
            "seal_sha256": seal,
            "status": "PLUMB_DIGEST_MATCH",
            "trust_sha256": TRUST_SHA256,
            "vm_digest_match": True,
        }
        write_evidence(evidence / "gcp-lab-rows.json", result)
        print(json.dumps(result))
        return 0
    finally:
        drop_guest_copies(evidence)
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


def _kernel_flags(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    flags: dict[str, Any] = {}
    for source, dest in (("btf", "kernel_btf"), ("bpffs", "kernel_bpffs"), ("cgroup_v2", "kernel_cgroup_v2")):
        if isinstance(payload.get(source), bool):
            flags[dest] = payload[source]
    lsm = payload.get("lsm")
    if isinstance(lsm, str) and re.fullmatch(r"[a-z0-9,]{0,80}", lsm):
        flags["kernel_lsm"] = lsm
    return flags


def _finish_repeat(
    summary: dict[str, Any],
    *,
    enterprise_rc: int,
    descendant_rc: int,
    observed: bool,
    repeat: int,
    rows: dict[str, Any] | None,
) -> dict[str, Any]:
    summary.update(
        {
            "battery": "descendant-b1",
            "descendant_rc": descendant_rc,
            "enterprise_rc": enterprise_rc,
            "reboot_observed": observed,
            "repeat": repeat,
            "seal_checked": True,
        }
    )
    if rows:
        summary["rows"] = rows
    return summary


def _run_one_battery(
    project: str,
    name: str,
    seal: str,
    evidence: Path,
    repeat: int,
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enterprise grant/revoke, then descendant-b1. A failed enterprise row does not skip the rest."""
    enterprise = _ssh_case(project, name, guest_command(seal, "enterprise"))
    enterprise_text = (enterprise.stdout or "") + (enterprise.stderr or "")
    kernel_path = evidence / "kernel-facts.json"
    raw = _pull_guest_json(project, name)
    if not isinstance(raw, dict) or not isinstance(raw.get("revoke"), dict):
        parsed = _guest_payload(enterprise_text)
        if isinstance(parsed, dict) and isinstance(parsed.get("revoke"), dict):
            raw = parsed
    got_kernel = _scp_from(project, name, "/tmp/gcp-kernel-facts.json", kernel_path)
    if enterprise.returncode != 0:
        print(redact(enterprise_text)[-1500:], file=sys.stderr)
    hold = _enterprise_hold(raw if isinstance(raw, dict) else None)
    ledger = raw.get("z_ledger") if isinstance(raw, dict) else None
    summary: dict[str, Any] = {
        "denied_rows": 1 if hold["hold"] else 0,
        "deny_hold": hold["hold"],
        "deny_pid": hold["pid"],
        "errno": hold["errno"],
        "lineage_anchor": hold["lineage_anchor"],
        "path": CEILING_PATH,
    }
    captures.append(
        {
            "errno": hold["errno"],
            "fail_reasons": _enterprise_fail_reasons(raw if isinstance(raw, dict) else None)
            if enterprise.returncode != 0
            else [],
            "guest_rc": enterprise.returncode,
            "hold": hold["hold"],
            "lineage_anchor": hold["lineage_anchor"],
            "name": f"enterprise-{repeat}",
            "path": CEILING_PATH,
            "pid": hold["pid"],
            "uid": 65534,
        }
    )
    if _transport_failure(enterprise) and not hold["hold"]:
        summary["infra"] = True
    if isinstance(ledger, dict) and isinstance(ledger.get("bpftool_rc"), int):
        summary["bpftool_rc"] = ledger["bpftool_rc"]
    if isinstance(ledger, dict) and isinstance(ledger.get("loader_running"), bool):
        summary["loader_running"] = ledger["loader_running"]
    if got_kernel and kernel_path.is_file():
        summary.update(_kernel_flags(_load_json_file(kernel_path)))
    grant_probe = raw.get("grant_probe") if isinstance(raw, dict) else {}
    grant_errno = grant_probe.get("nobody_errno") if isinstance(grant_probe, dict) else -1
    if not isinstance(grant_errno, int) or isinstance(grant_errno, bool):
        grant_errno = -1
    enterprise_rows = allow_battery(
        {
            "grant": {
                "probe": {
                    "nobody_errno": grant_errno,
                    "result": "open_ok" if grant_errno == 0 else "open_error",
                }
            },
            "image": IMAGE_NAME,
            "revoke": {
                "probe": {
                    "nobody_errno": hold["errno"],
                    "result": "open_error" if hold["errno"] == 13 else "open_ok",
                }
            },
        }
    )
    before = _wait_ssh(project, name, SSH_WAIT_SECONDS)
    pre = _ssh_case(project, name, guest_command(seal, "descendant-b1", "pre"))
    pre_text = (pre.stdout or "") + (pre.stderr or "")
    # Pull while the guest is still up. The reboot is scheduled after the shell returns.
    pre_guest = _with_descendant_cases(_pull_guest_json(project, name), pre_text)
    pre_cases = _descendant_cases(pre_guest)
    after = _wait_boot(project, name, before, REBOOT_WAIT_SECONDS)
    if after and not _ssh_ready(project, name):
        after = ""
    observed = reboot_ready(before, after)
    failed = []
    not_run = []
    if isinstance(pre_guest, dict):
        body = pre_guest.get("pre") if isinstance(pre_guest.get("pre"), dict) else pre_guest
        if isinstance(body, dict) and isinstance(body.get("failed_cases"), list):
            failed = [item for item in body["failed_cases"] if isinstance(item, str)]
        not_run = body.get("not_run") if isinstance(body, dict) else []
    pre_rc = _py_rc(pre_text)
    held_case = next(
        (
            item
            for item in pre_cases
            if item.get("expect_deny") is True
            and item.get("pass") is True
            and isinstance(item.get("pid"), int)
            and item["pid"] > 0
            and isinstance(item.get("lineage_anchor"), int)
            and item["lineage_anchor"] > 0
        ),
        None,
    )
    if held_case and not summary.get("desc_deny_pid"):
        summary["desc_deny_pid"] = held_case["pid"]
        summary["desc_lineage_anchor"] = held_case["lineage_anchor"]
        summary["desc_denied_rows"] = 1
    pre_capture: dict[str, Any] = {
        "cases": pre_cases,
        "failed_cases": failed,
        "not_run": [item for item in not_run if isinstance(item, str)] if isinstance(not_run, list) else [],
        "guest_rc": pre_rc if pre_rc is not None else pre.returncode,
        "hold": _pre_held(pre_cases),
        "name": f"descendant-pre-{repeat}",
        "path": CEILING_PATH,
    }
    if held_case:
        pre_capture["lineage_anchor"] = held_case["lineage_anchor"]
        pre_capture["pid"] = held_case["pid"]
    captures.append(pre_capture)
    if not observed:
        print(redact(pre_text)[-1500:], file=sys.stderr)
        if _boot_lockout(project, name):
            captures.append(
                {
                    "fail_reasons": ["boot_lockout"],
                    "hold": False,
                    "name": f"reboot-{repeat}",
                }
            )
            raise SystemExit("safety")
        if _transport_failure(pre) and not pre_cases:
            summary["descendant_infra"] = True
        return _finish_repeat(
            summary,
            enterprise_rc=enterprise.returncode,
            descendant_rc=pre_rc if pre_rc is not None else pre.returncode,
            observed=False,
            repeat=repeat,
            rows=enterprise_rows,
        )
    post = _ssh_case(project, name, guest_command(seal, "descendant-b1", "post"))
    post_text = (post.stdout or "") + (post.stderr or "")
    if post.returncode != 0:
        print(redact(post_text)[-1500:], file=sys.stderr)
    guest = _pull_guest_json(project, name)
    if not isinstance(guest, dict) or not isinstance(guest.get("post"), dict):
        parsed = _guest_payload(post_text)
        if isinstance(parsed, dict) and isinstance(parsed.get("post"), dict):
            guest = parsed
    post_cases = _descendant_cases({"post": guest.get("post")} if isinstance(guest, dict) else None)
    if isinstance(guest, dict):
        nested = allow_battery(guest) or {}
        summary.update(nested)
        held_case = next(
            (
                item
                for item in post_cases
                if item["expect_deny"] and item["pass"] and item["pid"] and item["lineage_anchor"]
            ),
            None,
        )
        if held_case is None:
            held_case = next(
                (
                    item
                    for item in pre_cases
                    if item["expect_deny"] and item["pass"] and item["pid"] and item["lineage_anchor"]
                ),
                None,
            )
        if held_case:
            summary["desc_deny_pid"] = held_case["pid"]
            summary["desc_lineage_anchor"] = held_case["lineage_anchor"]
            summary["desc_denied_rows"] = 1
    captures.append(
        {
            "cases": post_cases,
            "failed_cases": [
                item["name"] for item in post_cases if item["expect_deny"] and not item["pass"]
            ],
            "guest_rc": _py_rc(post_text) if _py_rc(post_text) is not None else post.returncode,
            "hold": summary.get("b1_pass") is True,
            "lineage_anchor": summary.get("desc_lineage_anchor") or 0,
            "name": f"descendant-post-{repeat}",
            "path": CEILING_PATH,
            "pid": summary.get("desc_deny_pid") or 0,
        }
    )
    post_rc = _py_rc(post_text)
    if _transport_failure(post) and not post_cases:
        summary["descendant_infra"] = True
    return _finish_repeat(
        summary,
        enterprise_rc=enterprise.returncode,
        descendant_rc=post_rc if post_rc is not None else post.returncode,
        observed=observed,
        repeat=repeat,
        rows=enterprise_rows,
    )


def _bpf_listed(text: str) -> bool:
    return any(part.strip() == "bpf" for part in text.split(","))


def _cmdline_bpf(cmdline: str) -> bool:
    for token in cmdline.split():
        if token.startswith("lsm=") and _bpf_listed(token.split("=", 1)[1]):
            return True
    return False


def lsm_confirm_ok(body: dict) -> bool:
    """True when the live LSM list and the cmdline both contain bpf as its own token."""
    result = body.get("host_result")
    stock = body.get("stock_lsm") if isinstance(body.get("stock_lsm"), str) else ""
    cmdline = body.get("cmdline") if isinstance(body.get("cmdline"), str) else ""
    if result == "LSM_ENABLED":
        return _bpf_listed(stock) and _cmdline_bpf(cmdline)
    if result != "LSM_ALREADY_ACTIVE":
        return False
    return _bpf_listed(stock) and _cmdline_bpf(cmdline)


def _bootchain_public(source: dict) -> dict:
    chain = source.get("bootchain") if isinstance(source.get("bootchain"), dict) else {}
    if not chain and isinstance(source.get("grub"), dict):
        nested = source["grub"].get("bootchain")
        chain = nested if isinstance(nested, dict) else {}
    keys = (
        "efi_kind",
        "efi_head",
        "stub_uuid",
        "stub_prefix",
        "configfile",
        "esp",
        "decision",
        "uuid_mount",
        "boot_uuid",
        "root_uuid",
        "esp_uuid",
        "grub_alias",
        "stock_line",
        "packages",
        "kernel",
        "grub_d",
        "rewritten",
        "error",
    )
    return {key: chain[key] for key in keys if key in chain}


def missing_rows_tail(stdout: str, stderr: str) -> str:
    """Redacted end of a guest run that never wrote a rows file."""
    tail = redact(((stdout or "") + "\n" + (stderr or "")).strip())
    return tail[-1200:]


def _print_saved_boot_evidence(project: str, name: str) -> None:
    """The reboot script writes this file after the last verify, before reset."""
    pulled = _ssh(
        project,
        name,
        "sudo cat /var/lib/vantio-lab/boot-evidence.json",
        timeout_s=PROBE_SSH_TIMEOUT,
    )
    print(
        json.dumps(
            {
                "boot_evidence_rc": pulled.returncode,
                "boot_evidence": (pulled.stdout or "")[:24000],
            }
        ),
        flush=True,
    )


def serial_port_argv(project: str, name: str, start: int | None = None) -> list[str]:
    argv = [
        "gcloud",
        "compute",
        "instances",
        "get-serial-port-output",
        name,
        f"--project={project}",
        f"--zone={ZONE}",
        "--port=1",
    ]
    if start is None:
        return argv
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise SystemExit("serial")
    argv.append(f"--start={start}")
    return argv


_SERIAL_NEXT = re.compile(r"Specify --start=(\d+) in the next get-serial-port-output")


def next_serial_start(text: str) -> int | None:
    """Byte offset gcloud prints when the serial buffer continues."""
    match = _SERIAL_NEXT.search(text or "")
    if match is None:
        return None
    return int(match.group(1))


def serial_console_text(blob: str) -> str:
    """Keep the serial text gcloud returned and drop its --start instruction.

    The GCE serial ring drops older bytes, so this is the retained window from
    the call. Run 38800477282's last 200000 characters hid the earlier boot
    because that capture waited until after the batteries.
    """
    kept: list[str] = []
    for line in blob.replace("\x00", "").splitlines(keepends=True):
        if "Specify --start=" in line and "get-serial-port-output" in line:
            continue
        kept.append(line)
    return "".join(kept)


def guard_ready(body: dict, boot_id: str) -> bool:
    """True when this boot's guard asked for a reboot.

    A rows file from an earlier boot must not schedule the wait.
    """
    return (
        isinstance(body, dict)
        and body.get("host_result") == "GUARD_PROVED"
        and body.get("reboot_requested") is True
        and confirm_matches_boot(body, boot_id)
    )


def choose_boot_rows(
    primary: dict | None,
    secondary: dict | None,
    boot_id: str,
) -> dict | None:
    """Prefer the rows file written on boot_id. Otherwise keep the var-lib copy."""
    if isinstance(primary, dict) and confirm_matches_boot(primary, boot_id):
        return primary
    if isinstance(secondary, dict) and confirm_matches_boot(secondary, boot_id):
        return secondary
    if isinstance(primary, dict):
        return primary
    if isinstance(secondary, dict):
        return secondary
    return None


def confirm_matches_boot(body: dict, boot_id: str) -> bool:
    """True when the rows file was written on the boot the runner just waited for.

    The pre-reboot guard writes GUARD_PROVED and the stock cmdline to
    /var/lib/vantio-lab/enterprise-pe-rows.json. A confirm that pulls that
    file reports the stock line while the new boot's kernel log has the
    sealed line.
    """
    got = body.get("boot_id") if isinstance(body, dict) else None
    return isinstance(got, str) and bool(boot_id) and "\n" not in boot_id and got == boot_id


def live_lsm_from_probe(probe: dict, boot_id: str) -> dict | None:
    """Confirm built from the live files when the rows file is an older boot.

    The probe has to be the boot the runner waited for, and bpf has to be its
    own token in both /proc/cmdline and /sys/kernel/security/lsm.
    """
    if not isinstance(probe, dict) or not confirm_matches_boot(probe, boot_id):
        return None
    cmdline = probe.get("cmdline") if isinstance(probe.get("cmdline"), str) else ""
    enabled = probe.get("enabled_lsm") if isinstance(probe.get("enabled_lsm"), str) else ""
    body = {
        "boot_id": probe.get("boot_id"),
        "cmdline": cmdline,
        "stock_lsm": enabled,
        "cmdline_has_bpf": _cmdline_bpf(cmdline),
        "host_result": "LSM_ENABLED",
        "kernel_command_lines": probe.get("kernel_command_lines") if isinstance(probe.get("kernel_command_lines"), list) else [],
        "grubenv": probe.get("grubenv") if isinstance(probe.get("grubenv"), list) else [],
    }
    if not lsm_confirm_ok(body):
        return None
    return body


def stock_bpf_ready(body: dict, boot_id: str) -> bool:
    """True when this boot's LSM list already contains bpf as its own token.

    A stock kernel can enable bpf without an lsm= cmdline word. The sealed
    reboot still has to show bpf in both places. That check is lsm_confirm_ok.
    """
    if not isinstance(body, dict) or not confirm_matches_boot(body, boot_id):
        return False
    if body.get("host_result") not in {"LSM_ALREADY_ACTIVE", "LSM_ENABLED"}:
        return False
    stock = body.get("stock_lsm") if isinstance(body.get("stock_lsm"), str) else ""
    return _bpf_listed(stock)


def live_stock_bpf(probe: dict, boot_id: str) -> dict | None:
    """Live LSM list for a stock host. Does not require an lsm= cmdline token."""
    if not isinstance(probe, dict) or not confirm_matches_boot(probe, boot_id):
        return None
    enabled = probe.get("enabled_lsm") if isinstance(probe.get("enabled_lsm"), str) else ""
    if not _bpf_listed(enabled):
        return None
    cmdline = probe.get("cmdline") if isinstance(probe.get("cmdline"), str) else ""
    return {
        "boot_id": probe.get("boot_id"),
        "cmdline": cmdline,
        "stock_lsm": enabled,
        "cmdline_has_bpf": _cmdline_bpf(cmdline),
        "host_result": "LSM_ALREADY_ACTIVE",
        "kernel_command_lines": probe.get("kernel_command_lines") if isinstance(probe.get("kernel_command_lines"), list) else [],
        "grubenv": probe.get("grubenv") if isinstance(probe.get("grubenv"), list) else [],
    }


LATER_BOOT_PROBE = (
    "sudo python3 -c \"import json,sys; sys.path.insert(0,'/var/lib/vantio-lab/guest'); "
    "import baseline_diag; "
    "print(json.dumps({'boot_id': baseline_diag.read_boot_id(), "
    "'cmdline': open('/proc/cmdline',encoding='utf-8').read().strip()[:1200], "
    "'enabled_lsm': open('/sys/kernel/security/lsm',encoding='utf-8').read().strip()[:1200], "
    "'kernel_command_lines': baseline_diag.read_kernel_command_lines(), "
    "'grubenv': baseline_diag.read_grubenv_assignments()}))\""
)


def read_serial_log(project: str, name: str) -> tuple[int, str, int, str]:
    """Read the retained serial window.

    gcloud's --start hint is the next byte after this response. When the
    response already held the buffer, the next call only returns bytes written
    after it. Bytes the ring has already dropped do not come back. A timeout
    on a later page keeps the pages already read. The error name is empty when
    the walk finished on a non-empty window.
    """
    chunks: list[str] = []
    start: int | None = None
    seen: set[int] = set()
    rc = 0
    error = ""
    finished = False
    for _page in range(4):
        key = -1 if start is None else start
        if key in seen:
            finished = True
            break
        seen.add(key)
        try:
            proc = subprocess.run(
                serial_port_argv(project, name, start),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            error = "page_timeout"
            break
        except OSError:
            error = "page_error"
            break
        rc = proc.returncode
        raw = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        page = serial_console_text(raw)
        previous = chunks[-1] if chunks else ""
        if page and page != previous:
            chunks.append(page)
        nxt = next_serial_start(raw)
        if nxt is None or not page.strip() or (start is not None and nxt <= start) or (previous and page == previous):
            finished = True
            break
        start = nxt
    blob = "".join(chunks)
    if not error and not blob.strip():
        error = "empty"
    elif not error and not finished:
        error = "truncated"
    elif not error and rc != 0:
        error = "nonzero"
    return rc, blob, len(chunks), error


def _log_serial(project: str, name: str, boot_id: str = "") -> None:
    """Print the retained serial window before later guest output can fill it.

    A page error, an empty window, or a four-page cap is named on the
    SERIAL_ERROR line. The deliver step still returns success.
    """
    rc, blob, pages, error = read_serial_log(project, name)
    marker = f" SERIAL_ERROR={error}" if error else ""
    print(
        f"SERIAL_RC={rc} SERIAL_BYTES={len(blob)} SERIAL_PAGES={pages} SERIAL_BOOT={boot_id}{marker}",
        flush=True,
    )
    print(blob, flush=True)


def capture_serial(env: Mapping[str, str]) -> int:
    """Print the guest serial console while the instance still exists."""
    _require_execute(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    _log_serial(project, name)
    return 0


def _rows_for_boot(project: str, name: str, boot_id: str, transcript: str) -> dict[str, Any]:
    """The rows file written on boot_id. A surviving var-lib file loses to that boot's /tmp copy.

    The second copy is skipped when the var-lib file is already this boot.
    """
    primary = _pull_remote_json(project, name, ROWS_JSON)
    if isinstance(primary, dict) and confirm_matches_boot(primary, boot_id):
        return primary
    secondary = _pull_remote_json(project, name, "/tmp/enterprise-pe-rows.json")
    chosen = choose_boot_rows(primary, secondary, boot_id)
    if isinstance(chosen, dict) and chosen:
        return chosen
    parsed = _guest_payload(transcript)
    return parsed if isinstance(parsed, dict) else {}


def _probe_live(project: str, name: str) -> dict[str, Any]:
    probed = _ssh(project, name, LATER_BOOT_PROBE, timeout_s=PROBE_SSH_TIMEOUT)
    parsed = _last_object((probed.stdout or "") + (probed.stderr or ""))
    return parsed if isinstance(parsed, dict) else {}


def _prepare_lab_lsm(project: str, name: str, seal: str, evidence: Path) -> dict[str, Any]:
    """Record the stock LSM list. Enable bpf only after the loader refuses."""
    boot_before = _wait_live_boot(project, name, SSHD_WAIT_SECONDS)
    if not boot_before:
        write_evidence(
            evidence / "lsm-guard.json",
            {
                "host_result": "",
                "lsm_guard": "boot_id_unread",
                "stock_bpf_lsm": False,
                "stock_lsm": "",
            },
        )
        raise SystemExit("lsm")
    completed = _ssh_case(project, name, guest_command(seal, "lsm-guard"))
    body = _rows_for_boot(project, name, boot_before, (completed.stdout or "") + (completed.stderr or ""))
    rows_missing = not body
    if rows_missing:
        tail = missing_rows_tail(completed.stdout or "", completed.stderr or "")
        if tail:
            print(tail, file=sys.stderr)
    result = body.get("host_result") if isinstance(body.get("host_result"), str) else ""
    stock = body.get("stock_lsm") if isinstance(body.get("stock_lsm"), str) else ""
    record = {
        "host_result": result,
        "lsm_guard": "missing",
        "stock_bpf_lsm": False,
        "stock_lsm": stock,
    }
    grub = body.get("grub") if isinstance(body.get("grub"), dict) else {}
    reason = body.get("reason") if isinstance(body.get("reason"), str) else ""
    linux_lines = grub.get("linux_lines") if isinstance(grub.get("linux_lines"), list) else []
    summary = {
        "grub_error": grub.get("error") if isinstance(grub.get("error"), str) else "",
        "grub_updated": grub.get("updated") is True,
        "bootchain": _bootchain_public(grub),
        "linux_line": str(linux_lines[0])[:800] if linux_lines else "",
        "boot_files": grub.get("boot_files") if isinstance(grub.get("boot_files"), list) else [],
        "lsm_guard": result,
        "reason": reason,
        "stock_lsm": stock,
    }
    if rows_missing:
        summary["guest_rc"] = completed.returncode
        summary["rows"] = "missing"
    print(json.dumps(summary), flush=True)
    if result == "LSM_ALREADY_ACTIVE":
        if not stock_bpf_ready(body, boot_before):
            probe_body = _probe_live(project, name)
            print(json.dumps({"boot_id": boot_before, "live_probe": probe_body}), flush=True)
            adopted = live_stock_bpf(probe_body, boot_before)
            if adopted is None:
                record["lsm_guard"] = "stale_rows" if not confirm_matches_boot(body, boot_before) else "confirm_failed"
                write_evidence(evidence / "lsm-guard.json", record)
                raise SystemExit("lsm")
            body = adopted
            record["stock_lsm"] = adopted.get("stock_lsm") if isinstance(adopted.get("stock_lsm"), str) else ""
        _log_serial(project, name, boot_before)
        record["lsm_guard"] = "already_active"
        record["stock_bpf_lsm"] = True
        write_evidence(evidence / "lsm-guard.json", record)
        return record
    if not guard_ready(body, boot_before):
        record["lsm_guard"] = "stale_rows" if result == "GUARD_PROVED" else ("refused" if result else "missing")
        write_evidence(evidence / "lsm-guard.json", record)
        raise SystemExit("lsm")
    after = _wait_boot(project, name, boot_before, REBOOT_WAIT_SECONDS)
    if not after:
        write_evidence(evidence / "lsm-guard.json", record)
        raise SystemExit("lsm")
    _log_serial(project, name, after)
    confirmed = _ssh_case(project, name, guest_command(seal, "lsm-guard"))
    confirm_body = _rows_for_boot(
        project,
        name,
        after,
        (confirmed.stdout or "") + (confirmed.stderr or ""),
    )
    enabled = confirm_body.get("stock_lsm") if isinstance(confirm_body.get("stock_lsm"), str) else ""
    cmdline = confirm_body.get("cmdline") if isinstance(confirm_body.get("cmdline"), str) else ""
    matched = confirm_matches_boot(confirm_body, after)
    kernel_lines = confirm_body.get("kernel_command_lines")
    grubenv = confirm_body.get("grubenv")
    print(
        json.dumps(
            {
                "bootchain": _bootchain_public(confirm_body),
                "boot_id": confirm_body.get("boot_id") if isinstance(confirm_body.get("boot_id"), str) else "",
                "boot_match": matched,
                "cmdline": cmdline[:1200],
                "cmdline_has_bpf": confirm_body.get("cmdline_has_bpf") is True,
                "enabled_lsm": enabled,
                "grubenv": grubenv if isinstance(grubenv, list) else [],
                "kernel_command_lines": kernel_lines if isinstance(kernel_lines, list) else [],
                "lsm_confirm": confirm_body.get("host_result") if matched else "stale_rows",
            }
        ),
        flush=True,
    )
    _print_saved_boot_evidence(project, name)
    if not matched:
        probe_body: dict[str, Any] = {}
        probed = _ssh(project, name, LATER_BOOT_PROBE, timeout_s=PROBE_SSH_TIMEOUT)
        parsed = _last_object((probed.stdout or "") + (probed.stderr or ""))
        if isinstance(parsed, dict):
            probe_body = parsed
        print(
            json.dumps(
                {
                    "later_boot_id": after,
                    "later_probe": probe_body,
                    "rows_boot_id": confirm_body.get("boot_id") if isinstance(confirm_body.get("boot_id"), str) else "",
                }
            ),
            flush=True,
        )
        adopted = live_lsm_from_probe(probe_body, after)
        if adopted is None:
            record["lsm_guard"] = "stale_rows"
            write_evidence(evidence / "lsm-guard.json", record)
            raise SystemExit("lsm")
        confirm_body = adopted
    followed_up = False
    if not lsm_confirm_ok(confirm_body):
        if guard_ready(confirm_body, after):
            later = _wait_boot(project, name, after, REBOOT_WAIT_SECONDS)
            probe_body: dict[str, Any] = {}
            if later:
                _log_serial(project, name, later)
                probe_body = _probe_live(project, name)
            print(
                json.dumps(
                    {
                        "later_boot_id": later,
                        "later_probe": probe_body,
                    }
                ),
                flush=True,
            )
            adopted = live_lsm_from_probe(probe_body, later) if later else None
            if adopted is not None:
                confirm_body = adopted
                followed_up = True
        if not lsm_confirm_ok(confirm_body):
            record["lsm_guard"] = "confirm_failed"
            write_evidence(evidence / "lsm-guard.json", record)
            raise SystemExit("lsm")
    record["lsm_guard"] = "lsm_enabled_follow_up" if followed_up else "lsm_enabled"
    confirmed_result = confirm_body.get("host_result") if isinstance(confirm_body.get("host_result"), str) else ""
    if confirmed_result in {"LSM_ENABLED", "LSM_ALREADY_ACTIVE"}:
        record["host_result"] = confirmed_result
    confirmed_lsm = confirm_body.get("stock_lsm") if isinstance(confirm_body.get("stock_lsm"), str) else ""
    if confirmed_lsm:
        record["stock_lsm"] = confirmed_lsm
    record["stock_bpf_lsm"] = True
    write_evidence(evidence / "lsm-guard.json", record)
    return record


def run_batteries(env: Mapping[str, str]) -> int:
    _enabled(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    _gate_ok(env)
    if not batteries_requested(env):
        raise SystemExit("batteries")
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    seal = refuse_batteries(env)
    evidence = _evidence_dir(env)
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "gcp-guest-payload"
    debs = _stage_payload(env, payload_dir)
    captures: list[dict[str, Any]] = []
    try:
        _wait_until_running(project, name)
        made = _ssh(project, name, f"sudo mkdir -p /var/lib/vantio-lab && sudo rm -rf {GUEST_DIR} && sudo mkdir -p {GUEST_DIR} && sudo chown -R $(id -u):$(id -g) /var/lib/vantio-lab {GUEST_DIR} && chmod 755 /var/lib/vantio-lab {GUEST_DIR}")
        if made.returncode != 0:
            raise SystemExit("ssh")
        _scp_to(
            project,
            name,
            [
                payload_dir / "seal.oci.tar",
                payload_dir / "contract.tar",
                payload_dir / "enterprise-rows.sh",
                payload_dir / "descendant_b1.py",
                payload_dir / "descendant_probe",
                payload_dir / "phase2_host.py",
                payload_dir / "phase2_grade.py",
                payload_dir / "baseline_diag.py",
                payload_dir / "sticky_write.py",
                payload_dir / "debs.tar",
                payload_dir / "ca-certificates.crt",
            ],
        )
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        lsm = _prepare_lab_lsm(project, name, seal, evidence)
        repeats: list[dict[str, Any]] = []
        schedule = battery_schedule(BATTERY_REPEATS)
        if schedule != ["enterprise", "descendant-b1"] * BATTERY_REPEATS:
            raise SystemExit("repeats")
        for index in range(BATTERY_REPEATS):
            if index:
                back = _wait_live_boot(project, name, REBOOT_WAIT_SECONDS)
                print(json.dumps({"repeat": index + 1, "repeat_boot_id": back}), flush=True)
                if not back:
                    if _boot_lockout(project, name):
                        captures.append(
                            {
                                "fail_reasons": ["boot_lockout"],
                                "hold": False,
                                "name": f"repeat-{index + 1}",
                            }
                        )
                        raise SystemExit("safety")
                    captures.append(
                        {
                            "fail_reasons": ["host_down_after_reboot"],
                            "hold": False,
                            "name": f"repeat-{index + 1}",
                        }
                    )
                    break
            repeat = _run_one_battery(project, name, seal, evidence, index + 1, captures)
            repeats.append(repeat)
        passed = full_set_passes(repeats)
        kill = _loader_case(project, name, seal, "2d-crash-recovery")
        restart = _loader_case(project, name, seal, "2c-upgrade-rollback")
        loader_kill = kill["word"]
        loader_restart = restart["word"]
        captures.extend(
            [
                _loader_capture("loader-kill", kill),
                _loader_capture("loader-restart", restart),
            ]
        )
        cases: list[dict[str, Any]] = []
        for repeat in repeats:
            errno = repeat.get("errno")
            pid = repeat.get("deny_pid")
            anchor = repeat.get("lineage_anchor")
            if repeat.get("infra") is True:
                cases.append(_infra_case("enterprise"))
            else:
                cases.append(
                    _case_row(
                        "enterprise",
                        "held" if repeat.get("deny_hold") is True else "fail",
                        errno if isinstance(errno, int) and errno >= 0 else 256,
                        [pid] if isinstance(pid, int) and pid > 0 else [],
                        anchor if isinstance(anchor, int) else 0,
                    )
                )
            desc_pid = repeat.get("desc_deny_pid")
            desc_anchor = repeat.get("desc_lineage_anchor")
            if repeat.get("descendant_infra") is True:
                cases.append(_infra_case("descendant-b1"))
            else:
                cases.append(
                    _case_row(
                        "descendant-b1",
                        "held" if repeat.get("b1_pass") is True and isinstance(desc_pid, int) and desc_pid > 0 else "fail",
                        256,
                        [desc_pid] if isinstance(desc_pid, int) and desc_pid > 0 else [],
                        desc_anchor if isinstance(desc_anchor, int) else 0,
                    )
                )
        cases.append(_loader_result_row("loader-kill", loader_kill, kill["body"], "while_loader_up", "enrolled_after"))
        cases.append(_loader_result_row("loader-restart", loader_restart, restart["body"], "deny_before", "deny_after"))
        kill_body = kill.get("body") if isinstance(kill, dict) else None
        enrolled_after = kill_body.get("enrolled_after") if isinstance(kill_body, dict) else None
        probe_pid = enrolled_after.get("pid") if isinstance(enrolled_after, dict) else 0
        if isinstance(probe_pid, bool) or not isinstance(probe_pid, int) or probe_pid < 0:
            probe_pid = 0
        uninstall = _ssh(
            project,
            name,
            "sudo env "
            f"VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID={probe_pid} "
            f"bash {GUEST_DIR}/enterprise-rows.sh {seal} uninstall",
        )
        uninstall_text = (uninstall.stdout or "") + "\n" + (uninstall.stderr or "")
        uninstall_verified = uninstall.returncode == 0 and "UNINSTALL_VERIFIED" in uninstall_text
        post_kill_row = "deny_attr_post_kill pid " in uninstall_text
        result = {
            "batteries": True,
            "captures": captures,
            "cases": cases,
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "package_image": PACKAGE_IMAGE,
            "loader_kill": loader_kill,
            "loader_restart": loader_restart,
            "debs": debs,
            "deny_attr_post_kill": post_kill_row,
            "full_set": passed,
            "uninstall_verified": uninstall_verified,
            "image": IMAGE_NAME,
            "lsm_guard": lsm.get("lsm_guard") if isinstance(lsm.get("lsm_guard"), str) else "",
            "mode": "enterprise",
            "stock_bpf_lsm": lsm.get("stock_bpf_lsm") is True,
            "stock_lsm": lsm.get("stock_lsm") if isinstance(lsm.get("stock_lsm"), str) else "",
            "network": NETWORK,
            "public_ip": False,
            "repeats": repeats,
            "seal_sha256": seal,
            "snapshot": SNAPSHOT,
            "subnet": SUBNET,
            "trust_sha256": TRUST_SHA256,
        }
        print(json.dumps({"cases": cases, "loader_kill": loader_kill, "loader_restart": loader_restart}), flush=True)
        write_evidence(evidence / "guest-evidence.json", {"captures": captures, "claim_cap": CLAIM_CAP})
        if not passed or loader_kill != "held" or loader_restart != "held":
            write_evidence(evidence / "gcp-lab-rows.json", result)
            raise SystemExit("battery" if not passed else "loader")
        if not uninstall_verified or not post_kill_row:
            print(redact(uninstall_text)[-2000:], file=sys.stderr)
            write_evidence(evidence / "gcp-lab-rows.json", result)
            raise SystemExit("uninstall")
        write_evidence(evidence / "gcp-lab-rows.json", result)
        print(json.dumps({"full_set": True, "repeats": BATTERY_REPEATS, "claim_cap": CLAIM_CAP}))
        return 0
    finally:
        if captures:
            try:
                write_evidence(
                    evidence / "guest-evidence.json",
                    {"captures": captures, "claim_cap": CLAIM_CAP},
                )
            except SystemExit:
                pass
        drop_guest_copies(evidence)
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


def self_service_requested(env: Mapping[str, str]) -> bool:
    raw = env.get("SELF_SERVICE", "false").strip().lower()
    if raw not in ("true", "false"):
        raise SystemExit("self_service")
    return raw == "true"


def _self_service_rows(body: object) -> list[dict[str, str]]:
    if not isinstance(body, dict):
        return []
    rows: list[dict[str, str]] = []
    installer = body.get("installer")
    if isinstance(installer, list):
        for item in installer:
            if not isinstance(item, dict):
                continue
            reason = item.get("reason")
            rows.append(
                {
                    "phase": str(item.get("phase") or ""),
                    "protection": str(item.get("protection") or ""),
                    "reason": reason if isinstance(reason, str) else "",
                    "state": str(item.get("state") or ""),
                }
            )
    enrollment = body.get("enrollment")
    if isinstance(enrollment, dict):
        reason = enrollment.get("reason")
        rows.append(
            {
                "phase": "enrollment",
                "protection": "NONE",
                "reason": reason if isinstance(reason, str) else "",
                "state": str(enrollment.get("status") or "GAP"),
            }
        )
    return rows


def run_self_service(env: Mapping[str, str]) -> int:
    """Copy the staged installer and run it. Does not run enterprise rows."""
    _require_execute(env)
    if batteries_requested(env) or not self_service_requested(env):
        raise SystemExit("self_service")
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    seal = expected_seal(env)
    staged = Path(env.get("W3_SELF_SERVICE_DIR", ""))
    tar_path = staged / "self-service.tar"
    if not tar_path.is_file() or not (staged / "lab-artifact-trust.json").is_file():
        raise SystemExit("self_service_layout")
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    _wait_until_running(project, name)
    _wait_ssh(project, name, SSH_WAIT_SECONDS)
    made = _ssh(project, name, f"sudo mkdir -p /var/lib/vantio-lab && sudo rm -rf {GUEST_DIR} && sudo mkdir -p {GUEST_DIR} && sudo chown -R $(id -u):$(id -g) /var/lib/vantio-lab {GUEST_DIR} && chmod 755 /var/lib/vantio-lab {GUEST_DIR}")
    if made.returncode != 0:
        raise SystemExit("ssh")
    _scp_to(project, name, [tar_path])
    deb_dir = Path(env.get("DEB_DIR", ""))
    if deb_dir.is_dir() and any(deb_dir.glob("*.deb")):
        packed = Path(env.get("RUNNER_TEMP") or "/tmp") / "self-service-debs.tar"
        pack_debs(deb_dir, packed)
        _scp_to(project, name, [packed])
        ca_bundle = deb_dir / "ca-certificates.crt"
        if ca_bundle.is_file() and ca_bundle.stat().st_size >= 1000:
            _scp_to(project, name, [ca_bundle])
    script = (
        "set -euo pipefail; "
        f"tar -xf {GUEST_DIR}/self-service.tar -C {GUEST_DIR}; "
        f"if [ -f {GUEST_DIR}/self-service-debs.tar ]; then mkdir -p {GUEST_DIR}/debs; "
        f"tar -xf {GUEST_DIR}/self-service-debs.tar -C {GUEST_DIR}/debs; fi; "
        "sudo env "
        f"PYTHONPATH={GUEST_DIR} "
        "VANTIO_LAB_SCOPE=lab-nonprod "
        f"VANTIO_LAB_ARTIFACT_TRUST={GUEST_DIR}/lab-artifact-trust.json "
        f"VANTIO_LAB_DEV_TRUST={GUEST_DIR}/lab-dev-trust.json "
        f"VANTIO_LAB_ROOT={GUEST_DIR} "
        f"VANTIO_INSTALL_BUNDLE={GUEST_DIR}/bundle "
        f"VANTIO_POLICY_FILE={GUEST_DIR}/policy.json "
        f"VANTIO_SIGNATURE_FILE={GUEST_DIR}/signature.json "
        "VANTIO_STATE_DIR=/var/lib/vantio/install "
        "VANTIO_SELF_SERVICE_OUT=/tmp/self-service-rows.json "
        f"python3 {GUEST_DIR}/self_service.py"
    )
    if "--artifact-trust" in script or "--fixture-host" in script or "\n" in script:
        raise SystemExit("self_service_layout")
    _run_guest(project, name, f"bash -c {json.dumps(script)}", "self_service")
    evidence = _evidence_dir(env)
    local = evidence / "self-service-rows.json"
    pulled = _scp_from(project, name, "/tmp/self-service-rows.json", local)
    body = _load_json_file(local) if pulled else {}
    write_evidence(
        evidence / "gcp-lab-rows.json",
        {
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "mode": "self-service",
            "mutated": True,
            "network": NETWORK,
            "public_ip": False,
            "seal_sha256": seal,
            "self_service": _self_service_rows(body),
            "status": "SELF_SERVICE",
            "subnet": SUBNET,
        },
    )
    if local.is_file() and not local.is_symlink():
        local.unlink()
    print(json.dumps({"mode": "self-service", "status": "SELF_SERVICE"}))
    return 0


def remove_os_login_key() -> int:
    pub = Path.home() / ".ssh" / "google_compute_engine.pub"
    if not pub.is_file():
        return 0
    completed = _run(["gcloud", "compute", "os-login", "ssh-keys", "remove", f"--key-file={pub}", "--quiet"])
    if completed.returncode != 0:
        print(redact((completed.stderr or "")[-500:]), file=sys.stderr)
    return 0


def delete_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    delete_objects(handoff_objects(env), missing_ok=True)
    write_evidence(_evidence_dir(env) / "handoff-deleted.json", {"deleted": True, "bucket": BUCKET})
    return 0


def _creation_epoch(project: str, name: str) -> int | None:
    completed = _run(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            name,
            f"--project={project}",
            f"--zone={ZONE}",
            "--format=value(creationTimestamp)",
        ]
    )
    stamp = (completed.stdout or "").strip()
    if completed.returncode != 0 or not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def teardown_if_present(env: Mapping[str, str]) -> int:
    _require_execute(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    deleted = False
    skipped = False
    hours = Decimal("0")
    gross = Decimal("0")
    try:
        created = _creation_epoch(project, name)
        now = int(time.time())
        if created is not None and now >= created:
            hours = Decimal(now - created) / Decimal("3600")
        gross = estimate_gross_usd(hours)
        instances = _list_instances(project)
        matched = next((item for item in instances if item.get("name") == name), None)
        if matched is not None:
            if not lab.labels_owned(matched.get("labels"), name):
                skipped = True
            else:
                _run_ok(
                    [
                        "gcloud",
                        "compute",
                        "instances",
                        "delete",
                        name,
                        f"--project={project}",
                        f"--zone={lab.instance_zone(matched)}",
                        "--delete-disks=all",
                        "--quiet",
                    ],
                    "teardown",
                )
                deleted = True
    finally:
        delete_objects(handoff_objects(env), missing_ok=True)
    if skipped:
        write_evidence(
            _evidence_dir(env) / "teardown.json",
            {"claim_cap": CLAIM_CAP, "deleted": False, "name": name, "verify_status": "UNKNOWN"},
        )
        return 2
    os.environ["INSTANCE_NAME"] = name
    os.environ["GCP_LAB_PROJECT"] = project
    os.environ["GCP_LAB_EXECUTE"] = "1"
    verify: dict[str, Any] = {"status": "UNKNOWN"}
    verify_rc = 2
    for _ in range(12):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            verify_rc = lab.execute_verify(os.environ)
        try:
            parsed = json.loads(buffer.getvalue())
        except json.JSONDecodeError:
            parsed = {"status": "UNKNOWN"}
        if isinstance(parsed, dict):
            verify = parsed
        if verify_rc == 0 and verify.get("status") == "VERIFIED_REMOVED":
            break
        time.sleep(10)
    payload = {
        "claim_cap": CLAIM_CAP,
        "cost_basis": "e2-micro 0.0084 USD/h plus 10GB pd-balanced, against trial credit; not a billing export",
        "deleted": deleted,
        "estimated_gross_usd": _money(gross),
        "expected_oop_usd": "0",
        "hours": _money(hours),
        "name": name,
        "out_of_pocket_usd": "0",
        "verify": verify,
    }
    write_evidence(_evidence_dir(env) / "teardown.json", payload)
    print(json.dumps(payload))
    if verify.get("status") != "VERIFIED_REMOVED" or verify_rc != 0:
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    env = os.environ
    try:
        if command == "assert-bundle":
            return assert_bundle_command(env)
        if command == "upload-handoff":
            return upload_handoff(env)
        if command == "download-handoff":
            return download_handoff(env)
        if command == "hash-debs":
            return hash_debs(env)
        if command == "prune-evidence":
            directory = _evidence_dir(env)
            print(json.dumps({"kept": prune_evidence(directory)}))
            return 0
        if command == "check-dispatch":
            refuse_batteries(env)
            print(json.dumps({"batteries": batteries_requested(env), "seal_sha256": expected_seal(env)}))
            return 0
        if command == "create-instance":
            return create_instance(env)
        if command == "plumb-guest":
            return plumb_guest(env)
        if command == "run-batteries":
            return run_batteries(env)
        if command == "run-self-service":
            return run_self_service(env)
        if command == "run-redteam":
            return redteam_campaign.execute(env, sys.modules[__name__])
        if command == "delete-handoff":
            return delete_handoff(env)
        if command == "remove-oslogin-key":
            return remove_os_login_key()
        if command == "serial-console":
            return capture_serial(env)
        if command == "teardown-if-present":
            return teardown_if_present(env)
    except SystemExit as exc:
        reason = exc.code
        if reason not in (0, None):
            print(reason if isinstance(reason, str) else "failed", file=sys.stderr)
            return 2
        return 0
    print(USAGE, file=sys.stderr)
    return 2

