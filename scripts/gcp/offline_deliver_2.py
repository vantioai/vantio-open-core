def _json_delete(bucket: str, object_name: str, token: str, *, missing_ok: bool) -> None:
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}"
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60):
            return
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return
        print(redact(f"storage delete {exc.code}"), file=sys.stderr)
        raise SystemExit("storage_delete") from None


def upload_one(bucket: str, object_name: str, path: Path, *, max_bytes: int = MAX_SEAL_BYTES) -> str:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", str(path), dest])
    text = (completed.stderr or "") + (completed.stdout or "")
    kind = classify_gcloud_cp(completed.returncode, text)
    if kind == "uploaded":
        print(json.dumps({"object": object_name, "via": "gcloud"}))
        return "gcloud"
    if kind != "fallback_json":
        print(redact(text)[-2000:], file=sys.stderr)
        raise SystemExit("handoff_upload")
    print(json.dumps({"object": object_name, "via": "resumable", "reason": "storage.objects.get"}))
    token = _access_token()
    try:
        resumable_upload(bucket, object_name, path, token, max_bytes=max_bytes)
    finally:
        token = ""
    return "resumable"


def _missing_object(text: str) -> bool:
    """True only when gcloud says the object is gone.

    Strip gs:// URIs first. A run id such as 14042 contains the digits 404, and
    a 403 that quotes that URI must not count as a missing object. "command
    not found" is a failed delete, not a missing object.
    """
    without_uris = re.sub(r"gs://\S+", " ", text or "")
    lowered = without_uris.lower()
    if "command not found" in lowered or "no such file or directory" in lowered:
        return False
    if "matched no objects" in lowered:
        return True
    if re.search(r"(?<![0-9])404(?![0-9])", lowered):
        return True
    return "not found" in lowered


def delete_objects(names: Sequence[str], *, missing_ok: bool) -> None:
    uris = [f"gs://{BUCKET}/{name}" for name in names]
    completed = _run(["gcloud", "storage", "rm", *uris])
    text = (completed.stderr or "") + (completed.stdout or "")
    if completed.returncode == 0:
        return
    if missing_ok and _missing_object(text):
        return
    token = _access_token()
    try:
        for name in names:
            _json_delete(BUCKET, name, token, missing_ok=missing_ok)
    finally:
        token = ""


def _enabled(env: Mapping[str, str]) -> None:
    """The generic probe switch stays off. Offline delivery is its own switch."""
    _require_execute(env)
    capabilities = lab.load_capabilities()
    if capabilities.get("offline_delivery_enabled") is not True:
        raise SystemExit("offline_delivery_disabled")
    if capabilities.get("launch_enabled") is True:
        raise SystemExit("launch_enabled")


def _gate_ok(env: Mapping[str, str]) -> dict[str, Any]:
    try:
        gate = json.loads(env.get("GCP_LAB_GATE_JSON") or "")
    except json.JSONDecodeError:
        raise SystemExit("cost_gate") from None
    if not isinstance(gate, dict) or gate.get("expected_oop_usd") != "0" or gate.get("abort") is not False:
        raise SystemExit("cost_gate")
    return gate


def assert_bundle_command(env: Mapping[str, str]) -> int:
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    checked = assert_bundle_dir(directory, expected_seal(env))
    evidence = _evidence_dir(env)
    write_evidence(evidence / "bundle-digests.json", {**checked, "claim_cap": CLAIM_CAP})
    github_output("seal_sha256", checked["seal_sha256"])
    github_output("contract_sha256", checked["contract_sha256"])
    print(json.dumps(checked))
    return 0


def upload_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    names = list(object_names(env.get("GITHUB_RUN_ID", "")))
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    checked = assert_bundle_dir(directory, expected_seal(env))
    paths = [directory / "seal.oci.tar", directory / "contract.tar"]
    limits = [MAX_SEAL_BYTES, MAX_SEAL_BYTES]
    if brain_requested(env):
        brain_dir = Path(env.get("BRAIN_DIR", ""))
        try:
            rtbrain.verify_files(brain_dir)
        except ValueError:
            raise SystemExit("model_sha") from None
        brain_names = brain_object_names(env.get("GITHUB_RUN_ID", ""))
        names.extend(brain_names)
        paths.extend([brain_dir / rtbrain.MODEL_NAME, brain_dir / rtbrain.RUNTIME_NAME])
        limits.extend([rtbrain.MODEL_BYTES, rtbrain.RUNTIME_BYTES])
    public_pin = ""
    if batteries_requested(env):
        public_pin = verify_public_pin_file(directory / PUBLIC_PIN_FILE)
        names.append(public_pin_object_name(env.get("GITHUB_RUN_ID", "")))
        paths.append(directory / PUBLIC_PIN_FILE)
        limits.append(MAX_SEAL_BYTES)
    via = [
        upload_one(BUCKET, name, path, max_bytes=limit)
        for name, path, limit in zip(names, paths, limits)
    ]
    payload = {
        "bucket": BUCKET,
        "claim_cap": CLAIM_CAP,
        "contract_sha256": checked["contract_sha256"],
        "objects": list(names),
        "project_id": project,
        "seal_sha256": checked["seal_sha256"],
        "trust_sha256": checked["trust_sha256"],
        "via": via,
    }
    if public_pin:
        payload["public_pin_sha256"] = public_pin
    write_evidence(_evidence_dir(env) / "handoff.json", payload)
    github_output("seal_sha256", checked["seal_sha256"])
    github_output("contract_sha256", checked["contract_sha256"])
    print(json.dumps({"bucket": BUCKET, "prefix": require_run_id(env.get("GITHUB_RUN_ID", ""))}))
    return 0


def stream_media_download(bucket: str, object_name: str, path: Path, token: str, exact: int) -> None:
    if bucket != BUCKET or ".." in object_name or object_name.startswith("/") or exact < 1:
        raise SystemExit("object")
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}?alt=media"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as handle:
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > exact:
                    raise SystemExit("handoff_download")
                handle.write(chunk)
    except urllib.error.HTTPError as exc:
        print(redact(f"brain download {exc.code}"), file=sys.stderr)
        raise SystemExit("handoff_download") from None
    if written != exact:
        raise SystemExit("handoff_download")


def download_exact(bucket: str, object_name: str, path: Path, exact: int) -> None:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", dest, str(path)])
    if completed.returncode == 0 and path.is_file() and path.stat().st_size == exact:
        return
    text = (completed.stderr or "") + (completed.stdout or "")
    if "403" not in text and "storage.objects.get" not in text and completed.returncode != 0:
        print(redact(text)[-2000:], file=sys.stderr)
        raise SystemExit("handoff_download")
    token = _access_token()
    try:
        stream_media_download(bucket, object_name, path, token, exact)
    finally:
        token = ""


def download_one(bucket: str, object_name: str, path: Path) -> None:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", dest, str(path)])
    if completed.returncode == 0 and path.is_file() and path.stat().st_size > 0:
        return
    text = (completed.stderr or "") + (completed.stdout or "")
    if classify_gcloud_cp(completed.returncode, text) != "fallback_json" and completed.returncode != 0:
        if "403" not in text and "storage.objects.get" not in text:
            print(redact(text)[-2000:], file=sys.stderr)
            raise SystemExit("handoff_download")
    token = _access_token()
    try:
        json_media_download(bucket, object_name, path, token)
    finally:
        token = ""


def download_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    expected_contract = env.get("EXPECTED_CONTRACT_SHA256", "").strip()
    if HEX64_RE.fullmatch(expected_contract) is None:
        raise SystemExit("contract_sha")
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    directory.mkdir(parents=True, exist_ok=True)
    names = object_names(env.get("GITHUB_RUN_ID", ""))
    seal_path = directory / "seal.oci.tar"
    contract_path = directory / "contract.tar"
    try:
        download_one(BUCKET, names[0], seal_path)
        download_one(BUCKET, names[1], contract_path)
        seal = verify_seal_file(seal_path, expected_seal(env))
        fetched = env.get("FETCHED_SEAL", "").strip().lower()
        if fetched and fetched != seal:
            raise SystemExit("seal")
        contract = verify_contract_trust(contract_path, TRUST_SHA256)
        if contract != expected_contract:
            raise SystemExit("contract_sha")
        payload = {
            "claim_cap": CLAIM_CAP,
            "contract_sha256": contract,
            "deleted": True,
            "seal_sha256": seal,
            "trust_sha256": TRUST_SHA256,
        }
        if batteries_requested(env):
            pin_path = directory / PUBLIC_PIN_FILE
            download_one(BUCKET, public_pin_object_name(env.get("GITHUB_RUN_ID", "")), pin_path)
            payload["public_pin_sha256"] = verify_public_pin_file(pin_path)
        if brain_requested(env):
            brain_dir = Path(env.get("BRAIN_DIR", ""))
            brain_dir.mkdir(parents=True, exist_ok=True)
            brain_names = brain_object_names(env.get("GITHUB_RUN_ID", ""))
            download_exact(BUCKET, brain_names[0], brain_dir / rtbrain.MODEL_NAME, rtbrain.MODEL_BYTES)
            download_exact(BUCKET, brain_names[1], brain_dir / rtbrain.RUNTIME_NAME, rtbrain.RUNTIME_BYTES)
            try:
                rtbrain.verify_files(brain_dir)
            except ValueError:
                raise SystemExit("model_sha") from None
        write_evidence(_evidence_dir(env) / "download.json", payload)
        print(json.dumps(payload))
        return 0
    finally:
        delete_objects(handoff_objects(env), missing_ok=True)


def hash_debs(env: Mapping[str, str]) -> int:
    directory = Path(env.get("DEB_DIR", ""))
    rows = deb_manifest(directory)
    payload = {
        "claim_cap": CLAIM_CAP,
        "package_image": PACKAGE_IMAGE,
        "debs": rows,
        "snapshot": SNAPSHOT,
    }
    write_evidence(_evidence_dir(env) / "debs.json", payload)
    print(json.dumps({"count": len(rows), "snapshot": SNAPSHOT}))
    return 0


def _list_instances(project: str) -> list[dict[str, Any]]:
    completed = _run_ok(
        ["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"],
        "instances",
    )
    text = completed.stdout.strip()
    parsed = json.loads(text) if text else []
    if not isinstance(parsed, list):
        raise SystemExit("instances")
    return [item for item in parsed if isinstance(item, dict)]


def describe_boot_disk_argv(project: str, name: str) -> list[str]:
    return [
        "gcloud",
        "compute",
        "disks",
        "describe",
        name,
        f"--project={project}",
        f"--zone={ZONE}",
        "--format=json(sourceImage)",
    ]


def create_instance(env: Mapping[str, str]) -> int:
    _enabled(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    gate = _gate_ok(env)
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    instances = _list_instances(project)
    if lab.slot_occupied(instances):
        raise SystemExit("slot_occupied")
    now = int(env["GCP_LAB_NOW_EPOCH"]) if env.get("GCP_LAB_NOW_EPOCH") else int(time.time())
    minutes = lab.bounded_minutes(env.get("STOP_AFTER_MINUTES", "120"))
    if brain_requested(env):
        try:
            gross = rtbrain.assert_under_cap(rtbrain.BRAIN_MACHINE, minutes, rtbrain.BRAIN_DISK_GB)
        except ValueError:
            raise SystemExit("cost") from None
        machine = rtbrain.BRAIN_MACHINE
        disk = "30GB"
    else:
        gross = None
        machine = lab.MACHINE_TYPE
        disk = lab.BOOT_DISK_GB
    labels = offline_labels(now, minutes)
    plan = {
        "image_family": IMAGE_FAMILY,
        "image_project": IMAGE_PROJECT,
        "labels": labels,
        "name": name,
        "network": NETWORK,
        "project_id": project,
        "boot_disk_gb": disk,
        "machine_type": machine,
        "public_ip": False,
        "service_account": None,
        "subnet": SUBNET,
    }
    script_dir = Path(env.get("RUNNER_TEMP") or "/tmp")
    script_path = script_dir / "gcp-offline-startup.sh"
    script_path.write_text(offline_startup(minutes), encoding="utf-8")
    _run_ok(offline_create_argv(plan, str(script_path)), "create")
    described = _run(describe_boot_disk_argv(project, name))
    image_name = ""
    if described.returncode == 0 and (described.stdout or "").strip():
        try:
            image_name = image_name_from_disk(json.loads(described.stdout))
        except json.JSONDecodeError:
            image_name = ""
    payload = {
        "claim_cap": CLAIM_CAP,
        "expected_oop_usd": gate["expected_oop_usd"],
        "estimated_gross_usd": _money(gross) if gross is not None else _money(estimate_gross_usd(Decimal(minutes) / Decimal(60))),
        "image": f"{IMAGE_PROJECT}/{IMAGE_FAMILY}",
        "machine_type": machine,
        "name": name,
        "network": NETWORK,
        "project_id": project,
        "public_ip": False,
        "subnet": SUBNET,
        "zone": ZONE,
    }
    if image_name:
        payload["image_name"] = image_name
    write_evidence(_evidence_dir(env) / "instance.json", payload)
    github_output("instance_name", name)
    print(json.dumps(payload))
    return 0


def _transport_failure(completed: subprocess.CompletedProcess[str]) -> bool:
    """IAP or sshd died. That is not an open result from the guest."""
    if completed.returncode == 255:
        return True
    text = ((completed.stderr or "") + (completed.stdout or "")).lower()
    return any(
        marker in text
        for marker in (
            "4010",
            "destination read failed",
            "connection refused",
            "connection reset",
            "broken pipe",
            "operation timed out",
        )
    )


def _ssh(
    project: str,
    name: str,
    command: str,
    timeout_s: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run(iap_ssh_argv(project, name, command), timeout_s=timeout_s)


def _ssh_ready(project: str, name: str, timeout_s: int = SSHD_WAIT_SECONDS) -> bool:
    """Poll until sshd accepts a command. The wait backs off and stops at about five minutes."""
    deadline = time.time() + timeout_s
    delay = 5
    while time.time() < deadline:
        probe = _ssh(project, name, "true", timeout_s=PROBE_SSH_TIMEOUT)
        if probe.returncode == 0:
            return True
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 30)
    return False


def _ssh_case(project: str, name: str, command: str) -> subprocess.CompletedProcess[str]:
    """Run one guest command. A dead tunnel is one INFRA_RETRY after sshd is back."""
    completed = _ssh(project, name, command, timeout_s=CASE_SSH_TIMEOUT)
    text = (completed.stdout or "") + (completed.stderr or "")
    if _transport_failure(completed) and _py_rc(text) is None and _ssh_ready(project, name):
        print("INFRA_RETRY", flush=True)
        completed = _ssh(project, name, command, timeout_s=CASE_SSH_TIMEOUT)
    return completed


def _wait_ssh(project: str, name: str, timeout_s: int) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id", timeout_s=PROBE_SSH_TIMEOUT)
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and boot and "\n" not in boot:
            return boot
        last = redact((probe.stderr or "")[-400:])
        time.sleep(10)
    print(last, file=sys.stderr)
    raise SystemExit("ssh")


def _wait_boot(project: str, name: str, before: str, timeout_s: int) -> str:
    """Wait until sshd answers with a new boot id. Each poll is bounded so one hung tunnel cannot use the whole wait."""
    deadline = time.time() + timeout_s
    delay = 5
    while time.time() < deadline:
        probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id", timeout_s=PROBE_SSH_TIMEOUT)
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and reboot_ready(before, boot):
            return boot
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 30)
    return ""


def _wait_live_boot(project: str, name: str, timeout_s: int) -> str:
    """Wait until sshd returns a boot id. This does not require the id to change."""
    deadline = time.time() + timeout_s
    delay = 5
    while time.time() < deadline:
        probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id", timeout_s=PROBE_SSH_TIMEOUT)
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and boot and "\n" not in boot:
            return boot
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 30)
    return ""


def scp_remove_miss_is_ignorable(detail: str) -> bool:
    """gcloud exits 1 after a finished copy when OS Login key removal misses.

    Any other line keeps the failure.
    """
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    if not lines:
        return False
    saw = False
    for line in lines:
        lowered = line.lower()
        if "os-login.ssh-keys.remove" in lowered and "cannot find requested ssh key" in lowered:
            saw = True
            continue
        return False
    return saw


def _scp_to(project: str, name: str, sources: Sequence[Path]) -> None:
    for path in sources:
        completed = _run(iap_scp_argv(project, [str(path)], f"{name}:{GUEST_DIR}/{path.name}"))
        if completed.returncode == 0:
            continue
        detail = redact((completed.stderr or "") + (completed.stdout or ""))
        if scp_remove_miss_is_ignorable(detail):
            remote = shlex.quote(f"{GUEST_DIR}/{path.name}")
            probe = _ssh(project, name, f"stat -c %s {remote}", timeout_s=PROBE_SSH_TIMEOUT)
            if probe.returncode == 0 and (probe.stdout or "").strip() == str(path.stat().st_size):
                continue
        print(f"scp_failed {path.name} bytes={path.stat().st_size}", file=sys.stderr)
        if detail:
            print(detail[-2000:], file=sys.stderr)
        raise SystemExit("scp")


SCP_FROM_REMOTES = frozenset(
    {
        "/tmp/gcp-kernel-facts.json",
        "/tmp/gcp-plumb.json",
        "/tmp/redteam-rows.json",
        "/var/lib/vantio-lab/redteam-rows.json",
        ROWS_JSON,
    }
)


def _scp_from(project: str, name: str, remote: str, dest: Path, timeout_s: int | None = None) -> bool:
    if remote not in SCP_FROM_REMOTES:
        print(f"scp_refused remote={remote}", file=sys.stderr)
        raise SystemExit("scp")
    completed = _run(iap_scp_argv(project, [f"{name}:{remote}"], str(dest)), timeout_s=timeout_s)
    if completed.returncode == 0 and dest.is_file():
        return True
    detail = redact((completed.stderr or "") + (completed.stdout or ""))
    print(f"scp_failed from {remote}", file=sys.stderr)
    if detail:
        print(detail[-2000:], file=sys.stderr)
    return False


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


RAW_GUEST_NAMES = (
    "gcp-plumb.json",
    "enterprise-rows.json",
    "kernel-facts.json",
    "descendant-b1.json",
    "redteam-rows.json",
)


def _remove_evidence_path(path: Path) -> None:
    """Remove a file, directory, or symlink without following the link.

    Walk iteratively. shutil.rmtree recurses in Python and raises RecursionError
    on a deep tree, which would skip the rest of the evidence cleanup.
    """
    try:
        pending = [path]
        ordered: list[Path] = []
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            identity = str(current)
            if identity in seen:
                continue
            seen.add(identity)
            ordered.append(current)
            try:
                if current.is_symlink() or not current.is_dir():
                    continue
                pending.extend(current.iterdir())
            except OSError:
                continue
        for current in reversed(ordered):
            try:
                if current.is_symlink() or not current.is_dir():
                    current.unlink(missing_ok=True)
                else:
                    current.rmdir()
            except OSError:
                continue
    except Exception:
        return


def drop_guest_copies(directory: Path) -> None:
    """Guest files are folded into the redacted evidence JSON. The raw copies
    must not sit in the directory that becomes a public artifact."""
    for name in RAW_GUEST_NAMES:
        _remove_evidence_path(directory / name)
        _remove_evidence_path(directory / f"{name}.sha256")


def prune_evidence(directory: Path) -> list[str]:
    """Leave only allowlisted evidence files, rewritten through the key allowlist."""
    drop_guest_copies(directory)
    kept: list[str] = []
    try:
        for path in list(directory.iterdir()):
            try:
                if path.is_symlink() or path.is_dir() or not path.is_file():
                    _remove_evidence_path(path)
                    continue
                stem = path.name[:-7] if path.name.endswith(".sha256") else path.name
                if stem not in EVIDENCE_FILES:
                    _remove_evidence_path(path)
                    continue
                if path.suffix != ".json":
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    _remove_evidence_path(path)
                    _remove_evidence_path(path.with_name(path.name + ".sha256"))
                    continue
                if not isinstance(payload, dict):
                    _remove_evidence_path(path)
                    _remove_evidence_path(path.with_name(path.name + ".sha256"))
                    continue
                if path.name == "redteam-packet.json":
                    redteam_packet.write_packet(path, payload)
                    kept.append(path.name)
                    continue
                write_evidence(path, payload)
                kept.append(path.name)
            except (Exception, SystemExit):
                _remove_evidence_path(path)
                _remove_evidence_path(path.with_name(path.name + ".sha256"))
    finally:
        for path in list(directory.iterdir()):
            if path.is_symlink() or path.is_dir():
                _remove_evidence_path(path)
                continue
            if path.name.endswith(".sha256"):
                if not (directory / path.name[:-7]).is_file():
                    _remove_evidence_path(path)
                continue
            if path.name not in EVIDENCE_FILES:
                _remove_evidence_path(path)
    return sorted(kept)


def _stored_guest(path: Path, fallback: str) -> Any:
    if path.is_file():
        parsed = _load_json_file(path)
        if parsed is not None:
            return parsed
        return redact(path.read_text(encoding="utf-8", errors="replace")[-20000:])
    return redact(fallback[-8000:])


def _phase_scripts(env: Mapping[str, str]) -> tuple[Path, Path]:
    host = Path(env.get("PHASE2_HOST", "scripts/aws/lab-guests/phase2_host.py"))
    grade = Path(env.get("PHASE2_GRADE", "scripts/aws/lab-guests/phase2_grade.py"))
    if not host.is_file() or not grade.is_file():
        raise SystemExit("phase2")
    return host, grade


def _last_object(text: str) -> dict[str, Any] | None:
    start = text.rfind("{")
    while start >= 0:
        try:
            parsed = json.loads(text[start:])
        except json.JSONDecodeError:
            start = text.rfind("{", 0, start)
            continue
        if isinstance(parsed, dict):
            return parsed
        start = text.rfind("{", 0, start)
    return None


def _ndjson_pids(body: Mapping[str, Any] | None) -> list[int]:
    if not isinstance(body, dict):
        return []
    raw = body.get("ndjson_denied_pids")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, int) and not isinstance(item, bool) and item > 0][:8]


def _sample_held(sample: Mapping[str, Any] | None) -> bool:
    """Errno 13 on the signed ceiling, with a DENIED row for that same pid and anchor."""
    if not isinstance(sample, dict) or sample.get("file_errno") != 13 or sample.get("path") != CEILING_PATH:
        return False
    pid = sample.get("pid")
    anchor = sample.get("lineage_anchor")
    event = sample.get("deny_event")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
        return False
    if not isinstance(event, dict):
        return False
    return event.get("pid") == pid and event.get("lineage_anchor") == anchor and event.get("path") == CEILING_PATH


# GCP 2D restart rows (phase2_grade.restart_row_side / restart_row_cause). The
# guest waits RESTART_ROW_CAP_S for each deny row. The host re-grades the kept
# integers itself and never trusts the guest's booleans or late_s. A row after
# RESTART_ROW_LATE_S still counts, but the claim is then not "prompt".
RESTART_ROW_CAP_S = 15.0
RESTART_ROW_LATE_S = 5.0
RESTART_ROW_CAUSES = frozenset(
    {
        "anchor_not_carried",
        "errno_invalid",
        "errno_not_13",
        "guest_flag_mismatch",
        "not_blocked",
        "pid_mismatch",
        "row_absent_errno13",
        "row_not_new",
        "row_past_cap",
    }
)
RESTART_ROW_SIDES = ("before", "after")
RESTART_ROWS_MISSING = "restart_rows_missing"
LATE_CLAIM_SCOPE = "deny row within 15 s on e2-micro; not prompt"
_ISO_TS_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(\.\d{1,9})?\s*(Z|[+-]\d{2}:?\d{2})?"
)


def _restart_errno(value: object) -> bool:
    return type(value) is int and 0 <= value <= 4095


def _ts_seconds(value: object) -> float | None:
    """Epoch seconds for an ISO-8601 or epoch timestamp string, or None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _ISO_TS_RE.fullmatch(text)
    if match:
        import calendar

        year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
        try:
            whole = calendar.timegm((year, month, day, hour, minute, second, 0, 0, 0))
        except (OverflowError, ValueError):
            return None
        zone = match.group(8)
        offset = 0
        if zone and zone != "Z":
            digits = zone[1:].replace(":", "")
            offset = (int(digits[:2]) * 3600 + int(digits[2:]) * 60) * (1 if zone[0] == "+" else -1)
        return whole + float(match.group(7) or 0) - offset
    if re.fullmatch(r"\d{9,19}(\.\d{1,9})?", text):
        number = float(text)
        for scale in (1e9, 1e6, 1e3):
            if number > scale * 1e8:
                return number / scale
        return number
    return None


# Where ledger_latency_s came from. PE ledger rows (engine da961aa) carry no
# time field, so host_seen_at (the guest's clock when its poll first saw the
# row) is the usual source. That is an upper bound on when the row was written.
LEDGER_TS_FROM_ROW = "ledger_row"
LEDGER_TS_HOST_SEEN = "host_seen_at"
LEDGER_TS_SOURCES = (LEDGER_TS_FROM_ROW, LEDGER_TS_HOST_SEEN)


def ledger_latency(side: Mapping[str, Any]) -> tuple[float | None, str | None]:
    """(row time - probe_at in seconds, source), or (None, None). Evidence only, never graded.

    The row's own ledger_ts is used when it parses. Otherwise seen_at is used
    and the source says host_seen_at, so the number is never read as a ledger time.
    """
    probe = _ts_seconds(side.get("probe_at"))
    if probe is None:
        return None, None
    for key, source in (("ledger_ts", LEDGER_TS_FROM_ROW), ("seen_at", LEDGER_TS_HOST_SEEN)):
        stamp = _ts_seconds(side.get(key))
        if stamp is not None and abs(stamp - probe) <= 86400:
            return round(stamp - probe, 3), source
    return None, None


def ledger_latency_s(side: Mapping[str, Any]) -> float | None:
    """The seconds from ledger_latency, without the source."""
    return ledger_latency(side)[0]


def allow_restart_side(value: object) -> dict[str, Any] | None:
    """One side of the restart evidence with typed values only.

    A bool, str or float errno is dropped, and a dropped errno grades as errno_invalid.
    The guest's late_s is dropped too: the host derives lateness from wait_s.
    """
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    if _restart_errno(value.get("errno")):
        kept["errno"] = value["errno"]
    for key in ("anchor_match", "new_row", "pass", "pid_match", "row_seen"):
        if isinstance(value.get(key), bool):
            kept[key] = value[key]
    for key, high in (("anchor", 2**32), ("expected_anchor", 2**32), ("pid", 2**22), ("row_pid", 2**22)):
        if _int_in(value.get(key), 0, high):
            kept[key] = value[key]
    for key in ("map_rows", "map_rows_before", "row_count", "rows_before"):
        if _int_in(value.get(key), 0, 100000):
            kept[key] = value[key]
    # map_rows is cumulative for the pid. The host derives the after-restart
    # share itself and ignores the guest's map_rows_after_new.
    if "map_rows" in kept and "map_rows_before" in kept:
        kept["map_rows_after_new"] = max(0, kept["map_rows"] - kept["map_rows_before"])
    if _seconds(value.get("wait_s")):
        kept["wait_s"] = value["wait_s"]
    for key in ("ledger_ts", "probe_at", "seen_at"):
        item = value.get(key)
        if isinstance(item, str) and _EVENT_TIME_RE.fullmatch(item):
            kept[key] = item
    if value.get("cause") in RESTART_ROW_CAUSES:
        kept["cause"] = value["cause"]
    # The host sets ledger_ts_source itself and ignores the guest's label:
    # ledger_row only when it kept a ledger_ts that parses.
    if kept.get("row_seen") is True:
        parsed = _ts_seconds(kept.get("ledger_ts")) is not None
        kept["ledger_ts_source"] = LEDGER_TS_FROM_ROW if parsed else LEDGER_TS_HOST_SEEN
    latency, source = ledger_latency(kept) if kept.get("row_seen") is True else (None, None)
    if latency is not None:
        kept["ledger_latency_s"] = latency
        kept["ledger_latency_source"] = source
    return kept


def allow_restart_rows(value: object) -> dict[str, Any]:
    """The GCP 2D before/after restart evidence, or {} when the guest sent none."""
    if not isinstance(value, dict):
        return {}
    kept: dict[str, Any] = {}
    for side in RESTART_ROW_SIDES:
        item = allow_restart_side(value.get(side))
        if item is not None:
            kept[side] = item
    return kept


def _kill_restart_rows(body: object) -> dict[str, Any]:
    """The loader-kill body's enroll_restart.restart_rows for gcp-lab-rows.json."""
    restart = body.get("enroll_restart") if isinstance(body, dict) else None
    return allow_restart_rows(restart.get("restart_rows") if isinstance(restart, dict) else None)


def _restart_pos(value: object) -> bool:
    return type(value) is int and value > 0


def _restart_count(value: object) -> bool:
    return type(value) is int and value >= 0


def restart_row_cause(side: object) -> str | None:
    """The host's own grade of one side. It matches phase2_grade.restart_row_cause.

    errno 0 is always not_blocked. errno 13 with no row is row_absent_errno13,
    a row only after RESTART_ROW_CAP_S is row_past_cap, and a row that does not
    raise the count is row_not_new. pid, anchor and newness are recomputed from
    the integers; a guest boolean that disagrees is guest_flag_mismatch.
    """
    if not isinstance(side, dict):
        return "errno_invalid"
    errno = side.get("errno")
    if type(errno) is not int:
        return "errno_invalid"
    if errno == 0:
        return "not_blocked"
    if errno != 13:
        return "errno_not_13"
    wait = side.get("wait_s")
    if side.get("row_seen") is not True or type(wait) not in (int, float) or not 0 <= wait < float("inf"):
        return "row_absent_errno13"
    if wait > RESTART_ROW_CAP_S:
        return "row_past_cap"
    count, before = side.get("row_count"), side.get("rows_before")
    if not (_restart_count(count) and _restart_count(before) and count > before):
        return "row_not_new"
    pid = side.get("pid")
    if not (_restart_pos(pid) and side.get("row_pid") == pid):
        return "pid_mismatch"
    anchor, expected = side.get("anchor"), side.get("expected_anchor")
    if not _restart_pos(anchor) or (expected is not None and expected != anchor):
        return "anchor_not_carried"
    for key in ("new_row", "pid_match", "anchor_match"):
        if key in side and side[key] is not True:
            return "guest_flag_mismatch"
    return None


def restart_rows_cause(rows: Mapping[str, Any]) -> str | None:
    """None only when both sides held. Before-restart causes end in _before_restart.

    The after row's expected_anchor has to be the before row's anchor.
    """
    before, after = rows.get("before"), rows.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return RESTART_ROWS_MISSING
    cause = restart_row_cause(before)
    if cause is not None:
        return f"{cause}_before_restart"
    cause = restart_row_cause(after)
    if cause is not None:
        return cause
    if after.get("expected_anchor") != before.get("anchor"):
        return "anchor_not_carried"
    return None


def restart_rows_late_s(rows: Mapping[str, Any]) -> float | None:
    """The host's own lateness: the largest wait_s over RESTART_ROW_LATE_S on a side that held."""
    late = [
        float(side["wait_s"])
        for side in (rows.get(name) for name in RESTART_ROW_SIDES)
        if isinstance(side, dict) and restart_row_cause(side) is None and side["wait_s"] > RESTART_ROW_LATE_S
    ]
    return round(max(late), 3) if late else None


def kill_late_fields(rows: Mapping[str, Any]) -> dict[str, Any]:
    """Top-level gcp-lab-rows.json fields so a late GCP 2D hold is never read as prompt."""
    late = restart_rows_late_s(rows)
    fields: dict[str, Any] = {"loader_kill_late_s": late}
    if late is not None:
        fields["loader_kill_claim_scope"] = LATE_CLAIM_SCOPE
    return fields


def _loader_word(mode: str, body: Mapping[str, Any] | None) -> str:
    """Held only when the measured probe itself is denied. An older pid does not count.

    Anchor 0 or a missing baseline deny is an enrollment setup miss, not a kill or restart grade.
    """
    if not isinstance(body, dict):
        return "fail"
    if body.get("setup_invalid") is True:
        return "setup_invalid"
    if mode == "2d-crash-recovery":
        if not _sample_held(body.get("while_loader_up")):
            return "setup_invalid"
        restart = body.get("enroll_restart")
        if isinstance(restart, dict):
            # The same-process restart check has to hold, and its GCP restart
            # rows have to pass the host's own grade too.
            if restart.get("held") is not True:
                return "fail"
            if restart_rows_cause(allow_restart_rows(restart.get("restart_rows"))):
                return "fail"
        else:
            # GCP 2D needs the restart rows (restart_rows_missing).
            return "fail"
        unenrolled = body.get("unenrolled_after")
        if not isinstance(unenrolled, dict) or unenrolled.get("file_errno") != 0:
            return "fail"
        if _kill_after_held(body.get("enrolled_after")):
            return "held"
        return "fail"
    if mode == "2c-upgrade-rollback":
        if _is_image_cycle(body):
            return _image_cycle_word(body)
        if not _sample_held(body.get("deny_before")):
            return "setup_invalid"
        if _sample_held(body.get("deny_after")):
            return "held"
        return "fail"
    return "fail"


# phase2_host.run_2c returns phase2_grade.grade_image_cycle(): steps
# baseline/upgrade/rollback/reupgrade plus host_result and reasons. It has no
# deny_before/deny_after, so the legacy 2C mapping above always said
# setup_invalid (provision 39859707484). These reasons mean the cycle never
# had both images to run; anything else the host graded is a real FAIL.
IMAGE_CYCLE_SETUP_REASONS = frozenset(
    {"public_pin_absent", "public_pin_digest", "seal_absent", "seal", "cycle_incomplete"}
)
IMAGE_CYCLE_STEPS = CYCLE_STEP_NAMES


def _is_image_cycle(body: Mapping[str, Any]) -> bool:
    return body.get("battery") == "2c-upgrade-rollback" and "steps" in body and "host_result" in body


def _image_cycle_word(body: Mapping[str, Any]) -> str:
    """Held only when the host recorded the full cycle with upgrade_pass. No pass rule is added."""
    if body.get("host_result") == "RECORDED" and body.get("upgrade_pass") is True:
        return "held"
    if body.get("reason") in IMAGE_CYCLE_SETUP_REASONS:
        return "setup_invalid"
    return "fail"


# phase2_grade.grade_upgrade_rollback sets this reason on a RECORDED cycle.
# It starts with "upgrade_", so on a RECORDED body it must not be read as an
# upgrade-step fail. On any other body it is kept like every other reason.
IMAGE_CYCLE_OK_REASON = "upgrade_rollback_reupgrade"


def _image_cycle_reasons(body: Mapping[str, Any]) -> list[str]:
    """The host's fail reasons for the cycle. A RECORDED cycle has none.

    The single reason is used only when there is no reasons list and the
    body is not RECORDED. RECORDED means host_result, as in _image_cycle_word.
    """
    reasons = body.get("reasons")
    if not isinstance(reasons, list):
        recorded = body.get("host_result") == "RECORDED"
        reasons = [] if recorded else [body.get("reason")]
    return [item for item in reasons if isinstance(item, str) and re.fullmatch(r"[a-z0-9_]{1,40}", item)][:16]


def _image_cycle_cases(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One capture row per cycle step: enforcement errno and the host's first reason for that step."""
    steps = body.get("steps") if isinstance(body.get("steps"), list) else []
    reasons = _image_cycle_reasons(body)
    rows = []
    for step in steps:
        if not isinstance(step, dict) or step.get("name") not in IMAGE_CYCLE_STEPS:
            continue
        name = step["name"]
        mine = [item for item in reasons if item.startswith(f"{name}_")]
        row: dict[str, Any] = {
            "expect_deny": True,
            "name": name,
            "pass": not mine and step.get("file_errno") == 13 and step.get("attributed") is True,
            "path": CEILING_PATH,
        }
        errno = step.get("file_errno")
        if isinstance(errno, int) and not isinstance(errno, bool) and 0 <= errno <= 255:
            row["file_errno"] = errno
        if mine:
            row["reason"] = mine[0]
        rows.append(row)
    return rows


def _kill_after_held(sample: Mapping[str, Any] | None) -> bool:
    """A post-kill deny is held only when the pid and the lineage anchor are both named.

    That name is a ledger DENIED row, or a deny-attr row drained with the anchor.
    A map hit that names only the pid is not a hold.
    """
    return _sample_held(sample)


def _event_anchor(event: Mapping[str, Any] | None) -> tuple[int, int]:
    if not isinstance(event, dict):
        return 0, 0
    pid = event.get("Pid")
    if pid is None:
        pid = event.get("pid")
    anchor = event.get("lineage_anchor")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        pid = 0
    if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
        anchor = 0
    attempted = event.get("PathAttempted") or event.get("Payload") or event.get("path")
    matched = event.get("PolicyRuleMatched")
    denied = event.get("ActionTaken") == "DENIED" or (
        isinstance(matched, str) and matched.startswith("ENFORCE_DENIED:")
    )
    if not denied or attempted != CEILING_PATH:
        return 0, 0
    return pid, anchor


def _enterprise_hold(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """A revoke deny with pid and anchor is a hold even when the guest script exits 1."""
    revoke = raw.get("revoke") if isinstance(raw, dict) else None
    probe = revoke.get("probe") if isinstance(revoke, dict) else None
    event = revoke.get("block_event") if isinstance(revoke, dict) else None
    errno = probe.get("nobody_errno") if isinstance(probe, dict) else -1
    if not isinstance(errno, int) or isinstance(errno, bool):
        errno = -1
    pid, anchor = _event_anchor(event if isinstance(event, dict) else None)
    return {
        "errno": errno,
        "hold": errno == 13 and pid > 0 and anchor > 0,
        "lineage_anchor": anchor,
        "path": CEILING_PATH,
        "pid": pid,
        "uid": 65534,
    }


def _enterprise_fail_reasons(raw: Mapping[str, Any] | None) -> list[str]:
    # record_uninstall can leave {} plus uninstall_tail (and the census adds
    # removal) when guest_rows wrote nothing. That is still a missing guest JSON.
    if not isinstance(raw, dict) or "grant_loader" not in raw:
        return ["guest_json_missing"]
    reasons: list[str] = []
    grant = raw.get("grant_loader") if isinstance(raw.get("grant_loader"), dict) else {}
    if grant.get("rc") != 0:
        reasons.append("grant_loader")
    if grant.get("audit") is not True:
        reasons.append("grant_audit")
    if grant.get("path_observe") is not True:
        reasons.append("grant_observe")
    probe = raw.get("grant_probe") if isinstance(raw.get("grant_probe"), dict) else {}
    if probe.get("nobody_errno") != 0:
        reasons.append("grant_errno")
    unchanged = raw.get("unchanged") if isinstance(raw.get("unchanged"), dict) else {}
    if unchanged.get("conflict_reason") != "VERSION_CONFLICT":
        reasons.append("conflict_reason")
    if unchanged.get("generation") != unchanged.get("generation_before"):
        reasons.append("generation_moved")
    freeze = raw.get("freeze") if isinstance(raw.get("freeze"), dict) else {}
    if freeze.get("widen_reason") != "FROZEN":
        reasons.append("freeze_reason")
    unreachable = raw.get("unreachable") if isinstance(raw.get("unreachable"), dict) else {}
    if unreachable.get("reason") != "ENTERPRISE_UNREACHABLE":
        reasons.append("unreachable_reason")
    revoke = raw.get("revoke") if isinstance(raw.get("revoke"), dict) else {}
    revoke_probe = revoke.get("probe") if isinstance(revoke.get("probe"), dict) else {}
    if revoke_probe.get("nobody_errno") != 13:
        reasons.append("revoke_errno")
    removal = raw.get("removal") if isinstance(raw.get("removal"), dict) else {}
    if removal.get("verified_removed") is not True:
        reasons.append("programs_not_removed")
    return reasons


def _case_source(item: Mapping[str, Any]) -> Mapping[str, Any]:
    """Descendant stores the pid and anchor on each sample, under the case name."""
    samples = item.get("samples")
    if not isinstance(samples, list):
        return item
    chosen: Mapping[str, Any] | None = None
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        chosen = sample
        pid = sample.get("pid")
        if item.get("pass") is False and sample.get("file_errno") not in (0, None):
            break
        if sample.get("pass") is True and isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
            break
    if not isinstance(chosen, dict):
        return item
    merged = dict(chosen)
    if isinstance(item.get("name"), str):
        merged["name"] = item["name"]
    if isinstance(item.get("pass"), bool):
        merged["pass"] = item["pass"]
    return merged


def _case_capture(item: Mapping[str, Any]) -> dict[str, Any]:
    event = item.get("file_event") if isinstance(item.get("file_event"), dict) else {}
    anchor = event.get("lineage_anchor") if isinstance(event, dict) else 0
    if isinstance(anchor, bool) or not isinstance(anchor, int):
        anchor = 0
    row = {
        "expect_deny": item.get("expect_deny") is True,
        "file_errno": item.get("file_errno") if isinstance(item.get("file_errno"), int) else -1,
        "lineage_anchor": anchor,
        "name": item.get("name") if isinstance(item.get("name"), str) else "",
        "net_errno": item.get("net_errno") if isinstance(item.get("net_errno"), int) else -1,
        "pass": item.get("pass") is True,
        "path": CEILING_PATH,
        "pid": item.get("pid") if isinstance(item.get("pid"), int) else 0,
        "reason": item.get("reason") if isinstance(item.get("reason"), str) else "",
    }
    if item.get("skipped") is True:
        row["skipped"] = True
    return row


def boot_lockout(text: str) -> bool:
    """A guest that cannot boot or start sshd. A slow boot is not this."""
    low = text.lower()
    return any(
        marker in low
        for marker in (
            "you are in emergency mode",
            "kernel panic",
            "failed to start openssh",
            "sshd.service: failed",
            "dependency failed for openbsd secure shell",
        )
    )


def _boot_lockout(project: str, name: str) -> bool:
    """Read instance status and the serial console. Print a short excerpt."""
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
        ],
        timeout_s=60,
    )
    status = (described.stdout or "").strip()
    serial = _run(
        [
            "gcloud",
            "compute",
            "instances",
            "get-serial-port-output",
            name,
            f"--project={project}",
            f"--zone={ZONE}",
            "--port=1",
        ],
        timeout_s=60,
    )
    tail = (serial.stdout or "")[-2000:]
    print(f"BOOT_STATUS {status}", flush=True)
    print("SERIAL_EXCERPT_BEGIN", flush=True)
    print(redact(tail)[-1200:], flush=True)
    print("SERIAL_EXCERPT_END", flush=True)
    return boot_lockout(tail)


def _guest_payload(text: str) -> dict[str, Any] | None:
    """The last JSON object in a guest transcript. The Actions log drops the middle of a long print."""
    decoder = json.JSONDecoder()
    found: dict[str, Any] | None = None
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return found
        try:
            obj, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        index = start + max(consumed, 1)
        if isinstance(obj, dict):
            found = obj


def _with_descendant_cases(pulled: dict[str, Any] | None, text: str) -> dict[str, Any] | None:
    """The durable rows file. A transcript is not a second copy of that file."""
    del text
    return pulled if isinstance(pulled, dict) else None


def _pre_held(cases: list[dict[str, Any]]) -> bool:
    denied = [
        item
        for item in cases
        if item.get("expect_deny") is True and item.get("skipped") is not True
    ]
    if not denied:
        return False
    return all(
        item.get("pass") is True
        and isinstance(item.get("pid"), int)
        and not isinstance(item.get("pid"), bool)
        and item["pid"] > 0
        and isinstance(item.get("lineage_anchor"), int)
        and not isinstance(item.get("lineage_anchor"), bool)
        and item["lineage_anchor"] > 0
        for item in denied
    )


def _descendant_cases(raw: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    body = raw.get("pre") if isinstance(raw.get("pre"), dict) else raw
    cases = body.get("cases") if isinstance(body, dict) else None
    if not isinstance(cases, list):
        post = raw.get("post") if isinstance(raw.get("post"), dict) else None
        cases = post.get("cases") if isinstance(post, dict) else None
    if not isinstance(cases, list):
        return []
    return [_case_capture(_case_source(item)) for item in cases if isinstance(item, dict)]


def _py_rc(text: str) -> int | None:
    match = re.search(r"PY_RC=(\d+)", text)
    if match is None:
        return None
    return int(match.group(1))


def _collect_denied_pids(payload: Any, found: list[int] | None = None) -> list[int]:
    if found is None:
        found = []
    if isinstance(payload, dict):
        pid = payload.get("Pid")
        if payload.get("ActionTaken") == "DENIED" and isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 and pid not in found:
            found.append(pid)
        for value in payload.values():
            if len(found) >= 8:
                break
            _collect_denied_pids(value, found)
    elif isinstance(payload, list):
        for item in payload:
            if len(found) >= 8:
                break
            _collect_denied_pids(item, found)
    return found


def _probe_case(name: str, result: str, sample: Mapping[str, Any] | None) -> dict[str, Any]:
    errno = sample.get("file_errno") if isinstance(sample, dict) else -1
    pid = sample.get("pid") if isinstance(sample, dict) else 0
    anchor = sample.get("lineage_anchor") if isinstance(sample, dict) else 0
    if not isinstance(errno, int) or isinstance(errno, bool):
        errno = -1
    if not isinstance(pid, int) or isinstance(pid, bool):
        pid = 0
    if not isinstance(anchor, int) or isinstance(anchor, bool):
        anchor = 0
    return _case_row(name, result, errno, [pid] if pid > 0 else [], anchor)


def _loader_capture(name: str, case: Mapping[str, Any]) -> dict[str, Any]:
    body = case.get("body") if isinstance(case.get("body"), dict) else {}
    if name == "loader-restart" and _is_image_cycle(body):
        kept: dict[str, Any] = {
            "cases": _image_cycle_cases(body),
            "enforcement_drop": body.get("enforcement_drop") is True,
            "hold": case.get("word") == "held",
            "lineage_anchor": 0,
            "name": name,
            "path": CEILING_PATH,
            "pid": 0,
            "uid": 65534,
        }
        reasons = _image_cycle_reasons(body)
        if reasons and kept["hold"] is False:
            kept["fail_reasons"] = reasons
        # #362: pin residue is a named finding, not a fail. Keep it either way.
        findings = allow_cycle_findings(body.get("findings"))
        if findings:
            kept["findings"] = findings
        guest_rc = case.get("rc")
        if isinstance(guest_rc, int) and not isinstance(guest_rc, bool) and 0 <= guest_rc <= 255:
            kept["guest_rc"] = guest_rc
        return kept
    if name == "loader-kill":
        sample = body.get("enrolled_after") if isinstance(body.get("enrolled_after"), dict) else {}
        before = body.get("while_loader_up") if isinstance(body.get("while_loader_up"), dict) else {}
    else:
        sample = body.get("deny_after") if isinstance(body.get("deny_after"), dict) else {}
        before = body.get("deny_before") if isinstance(body.get("deny_before"), dict) else {}
    kept = {
        "cases": [
            _case_capture(
                {
                    "expect_deny": True,
                    "file_errno": before.get("file_errno"),
                    "file_event": before.get("deny_event"),
                    "name": "before",
                    "pass": _sample_held(before),
                    "pid": before.get("pid"),
                }
            ),
            _case_capture(
                {
                    "expect_deny": True,
                    "file_errno": sample.get("file_errno"),
                    "file_event": sample.get("deny_event"),
                    "name": "after",
                    "pass": _sample_held(sample),
                    "pid": sample.get("pid"),
                }
            ),
        ],
        "enforcement_drop": body.get("enforcement_drop") is True,
        "hold": case.get("word") == "held",
        "lineage_anchor": sample.get("lineage_anchor") if isinstance(sample.get("lineage_anchor"), int) else 0,
        "name": name,
        "path": CEILING_PATH,
        "pid": sample.get("pid") if isinstance(sample.get("pid"), int) else 0,
        "uid": 65534,
    }
    errno = sample.get("file_errno")
    if isinstance(errno, int) and not isinstance(errno, bool) and 0 <= errno <= 255:
        kept["errno"] = errno
    guest_rc = case.get("rc")
    if isinstance(guest_rc, int) and not isinstance(guest_rc, bool) and 0 <= guest_rc <= 255:
        kept["guest_rc"] = guest_rc
    if (
        name == "loader-kill"
        and kept["hold"] is False
        and _sample_held(before)
        and isinstance(sample, dict)
        and sample.get("file_errno") == 13
        and not _sample_held(sample)
    ):
        kept["fail_reasons"] = ["attribution_after_kill"]
    # 2D: the same-process restart check (phase2_host.same_process_across_restart).
    restart = body.get("enroll_restart") if isinstance(body.get("enroll_restart"), dict) else {}
    reason = restart.get("reason")
    if (
        kept["hold"] is False
        and isinstance(reason, str)
        and re.fullmatch(r"[a-z0-9_]{1,40}", reason)
        and restart.get("held") is not True
    ):
        kept["fail_reasons"] = [*kept.get("fail_reasons", []), reason]
    warnings = []
    for phase in ("before", "after"):
        wait = restart.get(f"{phase}_row_wait_s")
        seen = restart.get(f"{phase}_row_seen")
        if _seconds(wait):
            kept[f"{phase}_row_wait_s"] = wait
        if isinstance(seen, bool):
            kept[f"{phase}_row_seen"] = seen
        # Flag a late row here too, so the capture shows it even if the guest
        # output dropped its own warning.
        if seen is True and _seconds(wait) and wait > DENY_ROW_LATE_S:
            warnings.append(f"late_deny_row_{phase}_restart")
    for item in _allow_warnings(restart.get("warnings")) or []:
        if item not in warnings:
            warnings.append(item)
    if warnings:
        kept["warnings"] = warnings[:8]
    restart_rows = allow_restart_rows(restart.get("restart_rows"))
    if restart_rows:
        kept["restart_rows"] = restart_rows
        cause = restart_rows_cause(restart_rows)
        if cause is not None and kept["hold"] is False and cause not in kept.get("fail_reasons", []):
            kept["fail_reasons"] = [*kept.get("fail_reasons", []), cause]
        late = restart_rows_late_s(restart_rows)
        if late is not None:
            kept["late_s"] = late
            kept["claim_scope"] = LATE_CLAIM_SCOPE
    elif name == "loader-kill" and kept["hold"] is False:
        kept["fail_reasons"] = [*kept.get("fail_reasons", []), RESTART_ROWS_MISSING]
    return kept


def _case_row(name: str, result: str, errno: int, pids: list[int], anchor: int = 0) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case": name,
        "denied_rows": len(pids),
        "deny_pid": pids[-1] if pids else 0,
        "lineage_anchor": anchor if isinstance(anchor, int) and anchor > 0 else 0,
        "path": CEILING_PATH,
        "result": result,
    }
    if isinstance(errno, int) and not isinstance(errno, bool) and 0 <= errno <= 255:
        row["errno"] = errno
    return row


def _infra_case(name: str) -> dict[str, Any]:
    return {"case": name, "path": CEILING_PATH, "result": "infra_retry"}


def _loader_result_row(
    name: str,
    word: str,
    body: Mapping[str, Any] | None,
    before_key: str,
    after_key: str,
) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    if word == "infra_retry":
        return _infra_case(name)
    if word == "setup_invalid":
        sample = payload.get(before_key)
        return _setup_case(name, sample if isinstance(sample, dict) else None)
    sample = payload.get(after_key)
    return _probe_case(name, word, sample if isinstance(sample, dict) else None)


def _setup_case(name: str, sample: Mapping[str, Any] | None) -> dict[str, Any]:
    """Enrollment never started. Keep the pid and anchor, and do not store an errno grade."""
    pid = sample.get("pid") if isinstance(sample, dict) else 0
    anchor = sample.get("lineage_anchor") if isinstance(sample, dict) else 0
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
        pid = 0
    if not isinstance(anchor, int) or isinstance(anchor, bool) or anchor < 0:
        anchor = 0
    denied = isinstance(sample, dict) and isinstance(sample.get("deny_event"), dict)
    return {
        "case": name,
        "denied_rows": 1 if denied else 0,
        "deny_pid": pid,
        "lineage_anchor": anchor,
        "path": CEILING_PATH,
        "result": "setup_invalid",
    }


def _read_copied_rows(local: Path) -> dict[str, Any] | None:
    if not local.is_file():
        return None
    parsed = _load_json_file(local)
    return parsed if isinstance(parsed, dict) else None


def _pull_guest_json(project: str, name: str, timeout_s: int | None = None) -> dict[str, Any]:
    """The durable rows file. Missing and malformed are different failures."""
    local = Path(tempfile.mkdtemp(prefix="vantio-guest-")) / "rows.json"
    try:
        if not _scp_from(project, name, ROWS_JSON, local, timeout_s=timeout_s):
            raise SystemExit("rows_missing")
        text = local.read_text(encoding="utf-8")
        if not text.strip():
            raise SystemExit("rows_missing")
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            raise SystemExit("rows_malformed")
        if not isinstance(loaded, dict):
            raise SystemExit("rows_malformed")
        return loaded
    finally:
        shutil.rmtree(local.parent, ignore_errors=True)


def _pull_remote_json(project: str, name: str, remote: str) -> dict[str, Any] | None:
    local = Path(tempfile.mkdtemp(prefix="vantio-guest-")) / "rows.json"
    try:
        if not _scp_from(project, name, remote, local):
            return None
        return _read_copied_rows(local)
    finally:
        shutil.rmtree(local.parent, ignore_errors=True)


def _loader_case(project: str, name: str, seal: str, mode: str) -> dict[str, Any]:
    completed = _ssh_case(project, name, guest_command(seal, mode))
    text = (completed.stdout or "") + (completed.stderr or "")
    if _transport_failure(completed) and _py_rc(text) is None:
        body: dict[str, Any] = {"infra_retry": True}
    else:
        body = _pull_guest_json(project, name)
    word = "infra_retry" if body.get("infra_retry") is True else _loader_word(mode, body)
    sample = body.get("enrolled_after") if mode == "2d-crash-recovery" else body.get("deny_after")
    pid = sample.get("pid") if isinstance(sample, dict) else 0
    anchor = sample.get("lineage_anchor") if isinstance(sample, dict) else 0
    print(
        json.dumps(
            {
                "anchor": anchor if isinstance(anchor, int) else 0,
                "deny_pid": pid if isinstance(pid, int) else 0,
                "enforcement_drop": body.get("enforcement_drop") is True,
                "mode": mode,
                "rc": completed.returncode,
                "result": word,
            }
        ),
        flush=True,
    )
    if completed.returncode != 0 or word != "held":
        print(redact(text)[-1500:], file=sys.stderr)
    return {"body": body, "rc": completed.returncode, "word": word}


def _stage_payload(env: Mapping[str, str], dest: Path) -> list[dict[str, str]]:
    bundle = Path(env.get("W3_BUNDLE_DIR", ""))
    deb_dir = Path(env.get("DEB_DIR", ""))
    guest = Path(env.get("GUEST_SCRIPT", ""))
    descendant = Path(env.get("DESCENDANT_SCRIPT", ""))
    checked = assert_bundle_dir(bundle, expected_seal(env))
    if checked["contract_sha256"] != env.get("EXPECTED_CONTRACT_SHA256", "").strip():
        raise SystemExit("contract_sha")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(bundle / "seal.oci.tar", dest / "seal.oci.tar")
    shutil.copy2(bundle / "contract.tar", dest / "contract.tar")
    if batteries_requested(env):
        verify_public_pin_file(bundle / PUBLIC_PIN_FILE)
        shutil.copy2(bundle / PUBLIC_PIN_FILE, dest / PUBLIC_PIN_FILE)
        verify_public_pin_file(dest / PUBLIC_PIN_FILE)
    script_dest = dest / "enterprise-rows.sh"
    shutil.copy2(guest, script_dest)
    script_dest.chmod(0o755)
    shutil.copy2(descendant, dest / "descendant_b1.py")
    probe = descendant.parent / "descendant_probe"
    if not probe.is_file() or probe.stat().st_size < 1000:
        raise SystemExit("vfork_probe")
    shutil.copy2(probe, dest / "descendant_probe")
    (dest / "descendant_probe").chmod(0o755)
    host, grade = _phase_scripts(env)
    shutil.copy2(host, dest / "phase2_host.py")
    shutil.copy2(grade, dest / "phase2_grade.py")
    repo = Path(__file__).resolve().parents[2]
    shutil.copy2(repo / "scripts" / "release" / "pe_canonical_seal.py", dest / "pe_canonical_seal.py")
    shutil.copy2(repo / "release" / "pe-canonical-seal.json", dest / "pe-canonical-seal.json")
    shutil.copy2(repo / "release" / "pe-seal-history.json", dest / "pe-seal-history.json")
    guest_dir = host.parent
    shutil.copy2(guest_dir / "baseline_diag.py", dest / "baseline_diag.py")
    shutil.copy2(guest_dir / "sticky_write.py", dest / "sticky_write.py")
    # phase2_host.py imports this on the guest in 2c-upgrade-rollback.
    shutil.copy2(guest_dir / "product_uninstall_census.py", dest / "product_uninstall_census.py")
    rows = pack_debs(deb_dir, dest / "debs.tar")
    bundle = deb_dir / "ca-certificates.crt"
    if not bundle.is_file() or bundle.stat().st_size < 1000:
        raise SystemExit("ca_bundle")
    shutil.copy2(bundle, dest / "ca-certificates.crt")
    return rows


