# Part 4 of offline_deliver: the 2E, 2F, and 2G phase batteries on GCP.
#
# offline_deliver.py loads this file into the same namespace as parts 1-3.
# run_batteries (part 3) calls run_phase_batteries after its final authorized
# uninstall. Each phase runs scripts/aws/lab-guests/phase2_host.py on the
# guest, then its own authorized uninstall over a separate ssh call.
#
# Grading follows scripts/aws/w3_lab_steps.py phase_battery_verdict: the rows
# body decides, never the guest exit code or the workflow colour. The host
# then recomputes each result from the integers it kept. A guest boolean can
# only veto a pass (guest_flag_mismatch); it never makes one.


PHASE_MODES = ("2e-performance", "2f-tamper", "2g-distro")
# Copies of phase2_grade constants. test_gcp_phase_batteries.py asserts they match.
PHASE_MAX_PERF_SECONDS = 900
PHASE_PERF_SAMPLES = 100
PHASE_CLAIM_SCOPE_2F = "kill after deny-attr map swap; ready-to-swap gap not covered (VAN-45)"
PHASE_KILL_AFTER_MAP_SWAP = "after_map_swap"
PHASE_KILL_NOT_KILLED = "not_killed"
PHASE_DENY_SWAP_STEMS = ("vantio_deny_attr", "vantio_deny_attr_drops", "vantio_deny_overflow")
# One phase is one guest ssh call (CASE_SSH_TIMEOUT) plus its uninstall and two pulls.
PHASE_RESERVE_S = CASE_SSH_TIMEOUT + 300
# The guest powers off at stop_after_minutes. The deliver job stops at 110 minutes
# and creates the VM a few minutes in; serial capture and cleanup run after us.
PHASE_JOB_LIMIT_AFTER_CREATE_S = 105 * 60
PHASE_END_MARGIN_S = 300
PHASE_IMAGE = f"{IMAGE_PROJECT}/{IMAGE_FAMILY}"
PHASE_IMAGE_SOURCE_RE = re.compile(
    r"^(?:https://www\.googleapis\.com/compute/v1/)?projects/ubuntu-os-cloud/global/images/"
    r"(ubuntu-2404-[a-z0-9-]{1,80})$"
)
PHASE_RESULT_WORDS = frozenset({"PASS", "FAIL", "HOLD", "NOT_GRADED", "NOT_RUN"})
PHASE_WORD_RE = re.compile(r"^[a-z0-9_]{1,60}$")
PHASE_UPPER_RE = re.compile(r"^[A-Z0-9_]{1,40}$")
PHASE_PIN_RE = re.compile(
    r"^/sys/fs/bpf/(?:vantio_deny_attr|vantio_deny_attr_drops|vantio_deny_overflow)_incoming_[0-9]{1,10}$"
)
PHASE_DISTRO_RE = re.compile(r"^[A-Za-z0-9 ._()/+-]{1,80}$")
PHASE_KERNEL_RE = re.compile(r"^[A-Za-z0-9._+-]{1,80}$")
POST_KILL_RE = re.compile(r"^deny_attr_post_kill pid ([0-9]{1,10}) anchor ([0-9]{1,20})$", re.MULTILINE)
# 2G on GCP runs on the one image the lab already allows. The others are left out.
DISTRO_EXCLUDED = (
    {"distro": "debian-12", "reason": "not_lab_allowed_no_offline_package_set"},
    {"distro": "ubuntu-2204", "reason": "not_lab_allowed_no_offline_package_set"},
    {"distro": "rocky-9", "reason": "needs_20gb_disk_and_third_party_repo"},
    {"distro": "amazon-linux-2023", "reason": "not_published_on_gcp"},
    {"distro": "rhel-sles", "reason": "paid_image"},
)


def _int(value: Any, low: int = 0, high: int = 2**32) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if low <= value <= high else None


def _number(value: Any, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int) and value.bit_length() > 32:
        return None
    number = float(value)
    if number != number or not low <= number <= high:
        return None
    return value


def phase_egress_word(errno: Any) -> str:
    """phase2_grade.egress_word: EPERM, EACCES, or refused is a block. 0 is allowed."""
    if isinstance(errno, bool):
        return "no_response"
    if errno in (1, 13, 111):
        return "denied"
    if errno == 0:
        return "allowed"
    return "no_response"


def phase_side_pin_pid(path: Any) -> int | None:
    if not isinstance(path, str) or "_incoming_" not in path:
        return None
    tail = path.rsplit("_incoming_", 1)[1]
    if not tail.isdigit():
        return None
    pid = int(tail)
    return pid if pid > 0 else None


def phase_swap_owner(seen: Any, loaders: Any) -> bool:
    """phase2_grade.swap_owner_matches, recomputed from the kept pids."""
    if not isinstance(seen, list) or not isinstance(loaders, list) or len(loaders) != 1:
        return False
    owner = loaders[0]
    if not isinstance(owner, dict):
        return False
    pids = {pid for pid in (owner.get("host"), owner.get("ns")) if type(pid) is int and pid > 0}
    if not pids or not seen:
        return False
    return all(phase_side_pin_pid(path) in pids for path in seen)


def phase_map_swapped(before_ids: Any, before_incoming: Any, ids: Any, incoming: Any) -> bool:
    """phase2_grade.deny_map_swapped, recomputed from the kept map ids and pin paths."""
    if not isinstance(before_ids, dict) or not isinstance(ids, dict):
        return False
    if not isinstance(before_incoming, list) or not isinstance(incoming, list):
        return False
    if any(path not in before_incoming for path in incoming):
        return False
    for stem in PHASE_DENY_SWAP_STEMS:
        now = ids.get(stem)
        was = before_ids.get(stem)
        if type(now) is not int or now <= 0:
            return False
        if type(was) is int and was > 0 and now == was:
            return False
    return True


def _keep_pins(value: Any) -> list[str] | None:
    if not isinstance(value, list) or len(value) > 12:
        return None
    if not all(isinstance(item, str) and PHASE_PIN_RE.fullmatch(item) for item in value):
        return None
    return list(value)


def _keep_ids(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, int] = {}
    for stem in PHASE_DENY_SWAP_STEMS:
        number = _int(value.get(stem))
        if number is not None:
            kept[stem] = number
    return kept


def _keep_loaders(value: Any) -> list[dict[str, int]] | None:
    if not isinstance(value, list) or len(value) > 8:
        return None
    kept = []
    for item in value:
        if not isinstance(item, dict):
            return None
        host = _int(item.get("host"), 1, 2**22)
        ns = _int(item.get("ns"), 1, 2**22)
        if host is None or ns is None:
            return None
        kept.append({"host": host, "ns": ns})
    return kept


def allow_map_swap(value: Any) -> dict[str, Any]:
    """Keep the 2F map-swap facts the host needs to recompute the swap."""
    if not isinstance(value, dict):
        return {}
    kept: dict[str, Any] = {}
    if isinstance(value.get("swapped"), bool):
        kept["swapped"] = value["swapped"]
    reason = value.get("reason")
    if isinstance(reason, str) and PHASE_WORD_RE.fullmatch(reason):
        kept["reason"] = reason
    waited = _number(value.get("waited_s"), 0, 3600)
    if waited is not None:
        kept["waited_s"] = waited
    for key in ("before_ids", "ids"):
        ids = _keep_ids(value.get(key))
        if ids is not None:
            kept[key] = ids
    for key in ("incoming_before", "incoming", "incoming_seen"):
        pins = _keep_pins(value.get(key))
        if pins is not None:
            kept[key] = pins
    loaders = _keep_loaders(value.get("loaders"))
    if loaders is not None:
        kept["loaders"] = loaders
    return kept


def phase_verdict(row: Mapping[str, Any]) -> tuple[bool, str]:
    """AWS phase_battery_verdict, then the host's own recompute from kept integers."""
    battery = row.get("battery")
    if battery not in PHASE_MODES:
        return False, "battery_mismatch"
    host_result = row.get("host_result")
    if host_result == "NOT_RUN":
        reason = row.get("not_run_reason")
        return False, reason if isinstance(reason, str) and PHASE_WORD_RE.fullmatch(reason) else "not_run"
    if row.get("harness_error") is True:
        return False, "battery_harness_error"
    if host_result != "PASS":
        return False, {
            "NOT_GRADED": "battery_not_graded",
            "HOLD": "battery_hold",
            "FAIL": "battery_fail",
        }.get(host_result if isinstance(host_result, str) else "", "battery_result_unknown")
    if battery == "2f-tamper" and (
        row.get("kill_timing") != PHASE_KILL_AFTER_MAP_SWAP or row.get("claim_scope") != PHASE_CLAIM_SCOPE_2F
    ):
        return False, "claim_fields_missing"
    reason = {
        "2e-performance": _recompute_2e,
        "2f-tamper": _recompute_2f,
        "2g-distro": _recompute_2g,
    }[battery](row)
    if reason:
        return False, reason
    if row.get("uninstall_verified") is not True:
        return False, "uninstall_not_verified"
    return True, "battery_pass"


def _recompute_2e(row: Mapping[str, Any]) -> str:
    runtime = row.get("runtime_seconds")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)):
        return "host_runtime_missing"
    if not 0 <= runtime <= PHASE_MAX_PERF_SECONDS:
        return "host_runtime_bound"
    if row.get("host_count") != 1:
        return "host_count"
    count = row.get("sample_count")
    if count != PHASE_PERF_SAMPLES:
        return "host_sample_count"
    # Stricter than AWS: every timed sample is an enrolled open of the
    # signed path, so each one has to be a deny or the timing measured
    # something other than enforcement.
    if row.get("denied_samples") != count:
        return "host_denied_samples"
    if row.get("revoke_errno") != 13:
        return "host_revoke_not_converged"
    if row.get("revoke_fail_open") is not False:
        return "guest_flag_mismatch"
    return ""


def _recompute_2f(row: Mapping[str, Any]) -> str:
    swap = row.get("map_swap") if isinstance(row.get("map_swap"), dict) else {}
    if not phase_map_swapped(
        swap.get("before_ids"), swap.get("incoming_before"), swap.get("ids"), swap.get("incoming")
    ):
        return "host_map_swap_not_seen"
    if not phase_swap_owner(swap.get("incoming_seen"), swap.get("loaders")):
        return "host_swap_owner_mismatch"
    if swap.get("swapped") is not True:
        return "guest_flag_mismatch"
    if row.get("control_errno") != 0:
        return "host_control_not_allowed"
    net = row.get("enrolled_net_errno")
    anchor = row.get("net_block_anchor")
    denied = phase_egress_word(net) == "denied" or (
        net == 110 and isinstance(anchor, int) and not isinstance(anchor, bool) and anchor > 0
    )
    if not denied:
        return "host_enrolled_egress_not_denied"
    if row.get("enrolled_file_errno") != 13:
        return "host_file_not_denied"
    if row.get("allowlisted_private_errno") != 0:
        return "host_allowlisted_private_blocked"
    pid = row.get("enrolled_pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return "host_probe_pid_missing"
    # The host's attribution: the authorized uninstall drained a post-kill
    # deny-attr row naming this probe pid with a non-zero lineage anchor.
    if row.get("post_kill_pid") != pid or _int(row.get("post_kill_anchor"), 1, 2**63) is None:
        return "host_post_kill_row_missing"
    # The PASS body does not carry loader_up (grade_tamper holds when it is
    # true). A body that says the loader is up vetoes; one that says the
    # file deny is unattributed vetoes too.
    if row.get("loader_up") is True or row.get("file_attributed") is not True:
        return "guest_flag_mismatch"
    return ""


def _recompute_2g(row: Mapping[str, Any]) -> str:
    if row.get("image") != PHASE_IMAGE or row.get("boot_image_allowed") is not True:
        return "host_image_not_allowed"
    if row.get("seal_lane") is not True:
        return "host_seal_not_lane"
    for key in ("distro", "kernel", "kernel_lsm"):
        if not isinstance(row.get(key), str) or not row.get(key):
            return "host_missing_fields"
    if "bpf" not in str(row.get("kernel_lsm")).split(","):
        return "host_bpf_lsm_missing"
    pid = row.get("enrolled_pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return "host_probe_pid_missing"
    if row.get("enrolled_file_errno") != 13:
        return "host_enrolled_not_denied"
    if row.get("unenrolled_file_errno") != 0:
        return "host_unenrolled_not_allowed"
    if row.get("result") != "RECORDED" or row.get("kernel_btf") is not True:
        return "guest_flag_mismatch"
    return ""


def phase_row(
    mode: str,
    body: Mapping[str, Any] | None,
    *,
    guest_rc: int | None = None,
    uninstall_text: str = "",
    uninstall_rc: int | None = None,
    boot_source: str = "",
    seal_lane: bool = False,
    not_run_reason: str = "",
) -> dict[str, Any]:
    """The typed facts the host keeps from one phase. Guest strings are not copied raw."""
    row: dict[str, Any] = {"battery": mode}
    if not_run_reason:
        row["host_result"] = "NOT_RUN"
        row["not_run_reason"] = not_run_reason
        return allow_phase_row(row) or row
    body = body if isinstance(body, Mapping) else {}
    if body.get("battery") != mode:
        row["battery_seen"] = "mismatch"
    for key in ("host_result", "result", "reason", "classification"):
        if isinstance(body.get(key), str):
            row[key] = body[key]
    row["harness_error"] = bool(body.get("harness_error"))
    if guest_rc is not None:
        row["guest_rc"] = guest_rc
    if uninstall_rc is not None:
        row["uninstall_rc"] = uninstall_rc
    row["uninstall_verified"] = uninstall_rc == 0 and "UNINSTALL_VERIFIED" in uninstall_text.splitlines()
    post = POST_KILL_RE.findall(uninstall_text)
    if post:
        row["post_kill_pid"] = int(post[0][0])
        row["post_kill_anchor"] = int(post[0][1])
    if mode == "2e-performance":
        for key in (
            "runtime_seconds",
            "max_runtime_seconds",
            "sample_count",
            "host_count",
            "denied_samples",
            "revoke_convergence_ms",
            "revoke_errno",
            "revoke_fail_open",
        ):
            if key in body:
                row[key] = body[key]
    elif mode == "2f-tamper":
        enrolled = body.get("enrolled_after") if isinstance(body.get("enrolled_after"), dict) else {}
        row["enrolled_net_errno"] = enrolled.get("net_errno")
        row["enrolled_file_errno"] = enrolled.get("file_errno")
        row["enrolled_pid"] = enrolled.get("pid")
        for key in (
            "control_errno",
            "net_block_anchor",
            "allowlisted_private_errno",
            "loader_up",
            "file_attributed",
            "kill_timing",
            "claim_scope",
        ):
            if key in body:
                row[key] = body[key]
        row["map_swap"] = body.get("map_swap")
    elif mode == "2g-distro":
        facts = body.get("kernel_facts") if isinstance(body.get("kernel_facts"), dict) else {}
        enrolled = body.get("enrolled") if isinstance(body.get("enrolled"), dict) else {}
        unenrolled = body.get("unenrolled") if isinstance(body.get("unenrolled"), dict) else {}
        row["distro"] = facts.get("distro")
        row["kernel"] = facts.get("kernel")
        row["kernel_lsm"] = facts.get("lsm")
        row["kernel_btf"] = facts.get("btf")
        row["lockdown"] = facts.get("lockdown")
        row["enrolled_file_errno"] = enrolled.get("file_errno")
        row["unenrolled_file_errno"] = unenrolled.get("file_errno")
        row["enrolled_pid"] = enrolled.get("pid")
        row["attributed"] = body.get("attributed")
        row["image"] = PHASE_IMAGE
        matched = PHASE_IMAGE_SOURCE_RE.fullmatch(boot_source or "")
        row["boot_image_allowed"] = matched is not None
        if matched is not None:
            row["boot_image_name"] = matched.group(1)
        row["seal_lane"] = seal_lane is True
    return allow_phase_row(row) or {"battery": mode, "host_result": "", "pass": False, "verdict_reason": "battery_mismatch"}


def allow_phase_row(item: Any) -> dict[str, Any] | None:
    """Typed keys only. pass and verdict_reason are always recomputed here."""
    if not isinstance(item, dict) or item.get("battery") not in PHASE_MODES:
        return None
    kept: dict[str, Any] = {"battery": item["battery"]}
    if item.get("battery_seen") == "mismatch":
        kept["battery_seen"] = "mismatch"
    host_result = item.get("host_result")
    kept["host_result"] = host_result if host_result in PHASE_RESULT_WORDS else ""
    for key in ("reason", "classification", "not_run_reason"):
        value = item.get(key)
        if isinstance(value, str) and PHASE_WORD_RE.fullmatch(value):
            kept[key] = value
    result = item.get("result")
    if isinstance(result, str) and PHASE_UPPER_RE.fullmatch(result):
        kept["result"] = result
    for key in (
        "harness_error",
        "uninstall_verified",
        "revoke_fail_open",
        "loader_up",
        "file_attributed",
        "kernel_btf",
        "attributed",
        "boot_image_allowed",
        "seal_lane",
    ):
        if isinstance(item.get(key), bool):
            kept[key] = item[key]
    for key, low, high in (
        ("guest_rc", -1, 255),
        ("uninstall_rc", -1, 255),
        ("post_kill_pid", 1, 2**22),
        ("post_kill_anchor", 1, 2**63),
        ("max_runtime_seconds", 0, 86400),
        ("sample_count", 0, 100000),
        ("host_count", 0, 64),
        ("denied_samples", 0, 100000),
        ("revoke_errno", 0, 255),
        ("control_errno", 0, 255),
        ("enrolled_net_errno", 0, 255),
        ("enrolled_file_errno", 0, 255),
        ("unenrolled_file_errno", 0, 255),
        ("allowlisted_private_errno", 0, 255),
        ("enrolled_pid", 1, 2**22),
        ("net_block_anchor", 0, 2**63),
    ):
        number = _int(item.get(key), low, high)
        if number is not None:
            kept[key] = number
    for key, high in (("runtime_seconds", 86400), ("revoke_convergence_ms", 3_600_000)):
        number = _number(item.get(key), 0, high)
        if number is not None:
            kept[key] = number
    if item.get("kill_timing") in (PHASE_KILL_AFTER_MAP_SWAP, PHASE_KILL_NOT_KILLED):
        kept["kill_timing"] = item["kill_timing"]
    if item.get("claim_scope") == PHASE_CLAIM_SCOPE_2F:
        kept["claim_scope"] = PHASE_CLAIM_SCOPE_2F
    if item.get("battery") == "2f-tamper":
        swap = allow_map_swap(item.get("map_swap"))
        if swap:
            kept["map_swap"] = swap
    distro = item.get("distro")
    if isinstance(distro, str) and PHASE_DISTRO_RE.fullmatch(distro):
        kept["distro"] = distro
    kernel = item.get("kernel")
    if isinstance(kernel, str) and PHASE_KERNEL_RE.fullmatch(kernel):
        kept["kernel"] = kernel
    lsm = item.get("kernel_lsm")
    if isinstance(lsm, str) and re.fullmatch(r"[a-z0-9,]{1,80}", lsm):
        kept["kernel_lsm"] = lsm
    lockdown = lockdown_text(item.get("lockdown"))
    if lockdown:
        kept["lockdown"] = lockdown
    if item.get("image") == PHASE_IMAGE:
        kept["image"] = PHASE_IMAGE
    boot = item.get("boot_image_name")
    if isinstance(boot, str) and re.fullmatch(r"ubuntu-2404-[a-z0-9-]{1,80}", boot):
        kept["boot_image_name"] = boot
    if kept.get("battery_seen") == "mismatch":
        passed, reason = False, "battery_mismatch"
    else:
        passed, reason = phase_verdict(kept)
    kept["pass"] = passed
    kept["verdict_reason"] = reason
    return kept


def phases_pass(rows: Any) -> bool:
    """All three phases, in order, each a host-recomputed pass with a verified uninstall."""
    if not isinstance(rows, list) or len(rows) != len(PHASE_MODES):
        return False
    for mode, row in zip(PHASE_MODES, rows):
        kept = allow_phase_row(row)
        if kept is None or kept.get("battery") != mode or kept.get("pass") is not True:
            return False
    return True


def phase_verdict_line(row: Mapping[str, Any]) -> str:
    """The AWS BATTERY_VERDICT line for one phase, from the host-recomputed row."""
    host_result = row.get("host_result") or None
    line = (
        f"BATTERY_VERDICT battery={row.get('battery')} "
        f"host_result={host_result} pass={str(row.get('pass') is True).lower()} "
        f"reason={row.get('verdict_reason')} row_reason={row.get('reason') or '-'}"
    )
    if row.get("battery") == "2f-tamper":
        timing = row.get("kill_timing") or "-"
        scope = str(row.get("claim_scope") or "-").replace('"', "'")
        line += f' kill_timing={timing} claim_scope="{scope}"'
    return line


def report_phase_verdict(row: Mapping[str, Any]) -> str:
    line = phase_verdict_line(row)
    print(line, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
    return line


def phase_deadline(created_epoch: int | None, started_epoch: int, minutes: Any) -> int:
    """Last epoch second a phase may start its work. 0 when there is no budget."""
    try:
        bounded = lab.bounded_minutes(minutes)
    except ValueError:
        return 0
    base = created_epoch if isinstance(created_epoch, int) and 0 < created_epoch <= started_epoch else started_epoch
    end = min(base + bounded * 60, base + PHASE_JOB_LIMIT_AFTER_CREATE_S)
    return end - PHASE_END_MARGIN_S


def phase_has_time(deadline: int, now: float) -> bool:
    return deadline > 0 and deadline - now >= PHASE_RESERVE_S


def phase_command(seal: str, mode: str) -> str:
    if mode not in PHASE_MODES:
        raise SystemExit("battery")
    command = guest_command(seal, mode)
    if mode == "2g-distro":
        return f"env VANTIO_IMAGE_ID={PHASE_IMAGE} {command}"
    return command


def phase_uninstall_command(seal: str, require_row: bool, probe_pid: int) -> str:
    if HEX64_RE.fullmatch(seal) is None:
        raise SystemExit("seal")
    pid = probe_pid if isinstance(probe_pid, int) and not isinstance(probe_pid, bool) and probe_pid > 0 else 0
    return (
        "sudo env "
        f"VANTIO_REQUIRE_POST_KILL={'yes' if require_row else 'no'} VANTIO_PROBE_PID={pid} "
        f"bash {GUEST_DIR}/enterprise-rows.sh {seal} uninstall"
    )


def _lane_seal() -> str:
    try:
        import importlib.util

        path = Path(__file__).resolve().parents[2] / "scripts" / "release" / "pe_canonical_seal.py"
        spec = importlib.util.spec_from_file_location("pe_canonical_seal_host", path)
        if spec is None or spec.loader is None:
            return ""
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = module.lane_seal()
    except Exception:
        return ""
    return value if isinstance(value, str) and HEX64_RE.fullmatch(value) else ""


def _boot_source(project: str, name: str) -> str:
    described = _run(describe_boot_disk_argv(project, name))
    if described.returncode != 0:
        return ""
    try:
        payload = json.loads(described.stdout or "")
    except json.JSONDecodeError:
        return ""
    source = payload.get("sourceImage") if isinstance(payload, dict) else None
    return source.strip() if isinstance(source, str) and "\n" not in source.strip() else ""


def _run_one_phase(project: str, name: str, seal: str, mode: str) -> dict[str, Any]:
    completed = _ssh_case(project, name, phase_command(seal, mode))
    text = (completed.stdout or "") + (completed.stderr or "")
    guest_rc = _py_rc(text)
    if _transport_failure(completed) and guest_rc is None:
        body: dict[str, Any] | None = None
        missing = "transport"
    else:
        try:
            body, missing = _pull_guest_json(project, name), ""
        except SystemExit as exc:
            body, missing = None, exc.code if exc.code in ("rows_missing", "rows_malformed") else "rows_missing"
    if completed.returncode != 0 or body is None:
        print(redact(text)[-1500:], file=sys.stderr)
    probe_pid = 0
    if mode == "2f-tamper" and isinstance(body, dict) and isinstance(body.get("enrolled_after"), dict):
        raw = body["enrolled_after"].get("pid")
        probe_pid = raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else 0
    uninstall = _ssh(project, name, phase_uninstall_command(seal, mode == "2f-tamper", probe_pid))
    uninstall_text = (uninstall.stdout or "") + "\n" + (uninstall.stderr or "")
    if body is None:
        row = phase_row(mode, None, not_run_reason=missing)
        row["uninstall_verified"] = uninstall.returncode == 0 and "UNINSTALL_VERIFIED" in uninstall_text.splitlines()
        return allow_phase_row(row) or row
    row = phase_row(
        mode,
        body,
        guest_rc=guest_rc if guest_rc is not None else -1,
        uninstall_text=uninstall_text,
        uninstall_rc=uninstall.returncode if 0 <= uninstall.returncode <= 255 else -1,
        boot_source=_boot_source(project, name) if mode == "2g-distro" else "",
        seal_lane=mode == "2g-distro" and seal == _lane_seal(),
    )
    if row.get("uninstall_verified") is not True:
        print(redact(uninstall_text)[-1500:], file=sys.stderr)
    return row


def run_phase_batteries(
    project: str,
    name: str,
    seal: str,
    env: Mapping[str, str],
    *,
    ready: bool,
    started_epoch: int,
    now: Any = time.time,
) -> list[dict[str, Any]]:
    """2E, 2F, then 2G on the same VM. Each ends in its own authorized uninstall."""
    deadline = phase_deadline(_creation_epoch(project, name), started_epoch, env.get("STOP_AFTER_MINUTES", ""))
    rows: list[dict[str, Any]] = []
    blocked = "" if ready else "previous_uninstall"
    for mode in PHASE_MODES:
        if not blocked and not phase_has_time(deadline, now()):
            blocked = "time_budget"
        if blocked:
            row = phase_row(mode, None, not_run_reason=blocked)
        else:
            try:
                row = _run_one_phase(project, name, seal, mode)
            except (Exception, SystemExit) as exc:
                # The earlier batteries' rows still get written. A phase that
                # broke is not a result, and its uninstall is not known.
                print(f"phase {mode}: {type(exc).__name__}", file=sys.stderr)
                row = phase_row(mode, None, not_run_reason="phase_error")
            if row.get("uninstall_verified") is not True:
                # A leftover install would grade the next phase on a dirty host.
                blocked = "previous_uninstall"
        report_phase_verdict(row)
        rows.append(row)
    return rows
