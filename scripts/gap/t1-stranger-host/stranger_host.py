#!/usr/bin/env python3
"""Operator commands for a stranger-host evidence bundle.

These commands do not call AWS or GCP. Link-local image metadata is off
unless the operator passes --allow-metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bundle import assemble, dump, sha256_bytes, sign_bundle, verify_bundle
from capture import capture_boot, capture_uninstall, list_bpffs_pins, live_bpftool_text
from constants import CLAIM_AWAITING, CLAIM_FIXTURE, COMPARISON_SEAL, WORKING_SEAL
from errors import PackageError
from grade import grade_evidence
from preflight import collect_host, read_link_local_image


def _print_error(exc: PackageError) -> int:
    print(exc.reason, file=sys.stderr)
    return 1


def _load_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str, body: object) -> None:
    Path(path).write_text(dump(body), encoding="utf-8")


def _seal_record(path: str, digest: str) -> dict[str, object]:
    seal = Path(path) if path else None
    present = seal is not None and seal.is_file()
    file_sha = sha256_bytes(seal.read_bytes()) if present and seal is not None else ""
    matched = present and file_sha == digest
    return {
        "comparison_seal": digest == COMPARISON_SEAL,
        "digest": digest,
        "file_sha256": file_sha,
        "present": present,
        "sha256sum": "seal.oci.tar: OK" if matched else "seal.oci.tar: FAILED",
        "working_seal": digest == WORKING_SEAL,
    }


def command_preflight(args: argparse.Namespace) -> int:
    root = Path(args.root)
    live = root.resolve() == Path("/").resolve()
    metadata = ""
    if args.allow_metadata:
        metadata = read_link_local_image(urllib.request.urlopen)
    cgroup_name = None if live else args.cgroup_fstype
    try:
        host = collect_host(
            root,
            attestation=args.image_name,
            source=args.image_source,
            metadata=metadata,
            cgroup_name=cgroup_name,
        )
    except PackageError as exc:
        print(f"PREFLIGHT_FAIL {exc.reason}")
        return 1
    if args.out:
        _write(args.out, host)
    print("PREFLIGHT_OK")
    return 0


def command_capture_boot(args: argparse.Namespace) -> int:
    try:
        serial = Path(args.serial_file).read_text(encoding="utf-8", errors="replace")
        body = capture_boot(Path(args.root), serial)
    except PackageError as exc:
        return _print_error(exc)
    _write(args.out, body)
    if args.serial_out:
        Path(args.serial_out).write_text(str(body["serial_log"]), encoding="utf-8")
    print(body["boot_id"])
    return 0


def command_capture_uninstall(args: argparse.Namespace) -> int:
    try:
        text = Path(args.uninstall_out).read_text(encoding="utf-8", errors="replace")
        if args.live:
            bpftool = live_bpftool_text()
            pins = "\n".join(list_bpffs_pins(Path("/sys/fs/bpf")))
        else:
            if not args.bpftool_file or not args.pins_file:
                raise PackageError("bpftool_missing")
            bpftool = Path(args.bpftool_file).read_text(encoding="utf-8", errors="replace")
            pins = Path(args.pins_file).read_text(encoding="utf-8", errors="replace")
        fail_reasons = [item for item in args.fail_reason if item]
        body = capture_uninstall(
            uninstall_text=text,
            bpftool_text=bpftool,
            pin_listing=pins,
            fail_reasons=fail_reasons,
        )
    except PackageError as exc:
        return _print_error(exc)
    _write(args.out, body)
    print(body["uninstall_verified_line"])
    return 0


def _evidence_from_args(args: argparse.Namespace) -> dict[str, object]:
    boot = _load_json(args.boot)
    serial = Path(args.serial).read_text(encoding="utf-8", errors="replace") if args.serial else ""
    if not serial and isinstance(boot, dict) and isinstance(boot.get("serial_log"), str):
        serial = boot["serial_log"]
    return {
        "boot": boot,
        "descendant_post": _load_json(args.descendant_post),
        "descendant_pre": _load_json(args.descendant_pre),
        "enterprise": _load_json(args.enterprise),
        "host": _load_json(args.host_record),
        "seal": _seal_record(args.seal_file, args.seal_digest) if args.seal_digest else _load_json(args.seal_json),
        "serial": serial,
        "teardown": _load_json(args.teardown),
        "uninstall": _load_json(args.uninstall),
    }


def command_grade(args: argparse.Namespace) -> int:
    try:
        loaded = _evidence_from_args(args)
        graded = grade_evidence(
            host=loaded["host"],
            seal=loaded["seal"],
            enterprise=loaded["enterprise"],
            descendant_pre=loaded["descendant_pre"],
            boot=loaded["boot"],
            descendant_post=loaded["descendant_post"],
            uninstall=loaded["uninstall"],
            teardown=loaded["teardown"],
            serial_text=str(loaded["serial"]),
        )
    except PackageError as exc:
        return _print_error(exc)
    except (OSError, json.JSONDecodeError):
        print("input_missing", file=sys.stderr)
        return 1
    print(dump(graded), end="")
    return 0 if graded["result"] == "PASS" else 2


def command_assemble(args: argparse.Namespace) -> int:
    try:
        loaded = _evidence_from_args(args)
        graded = assemble(
            Path(args.out),
            host=loaded["host"],
            seal=loaded["seal"],
            enterprise=loaded["enterprise"],
            descendant_pre=loaded["descendant_pre"],
            boot=loaded["boot"],
            serial_text=str(loaded["serial"]),
            descendant_post=loaded["descendant_post"],
            uninstall=loaded["uninstall"],
            teardown=loaded["teardown"],
            claim=args.claim,
            created_utc=args.created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    except PackageError as exc:
        return _print_error(exc)
    except (OSError, json.JSONDecodeError):
        print("input_missing", file=sys.stderr)
        return 1
    print(graded["result"])
    return 0 if graded["result"] == "PASS" else 2


def command_sign(args: argparse.Namespace) -> int:
    try:
        sign_bundle(Path(args.bundle), Path(args.key), Path(args.trust), claim=args.claim)
    except PackageError as exc:
        return _print_error(exc)
    print(args.claim)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    try:
        result = verify_bundle(Path(args.bundle))
    except PackageError as exc:
        return _print_error(exc)
    print(dump(result), end="")
    grade = result["grade"]
    passed = isinstance(grade, dict) and grade.get("result") == "PASS"
    return 0 if passed else 2


def _add_evidence(parser: argparse.ArgumentParser, *, seal_file: bool) -> None:
    parser.add_argument("--host-record", required=True)
    parser.add_argument("--enterprise", required=True)
    parser.add_argument("--descendant-pre", required=True)
    parser.add_argument("--boot", required=True)
    parser.add_argument("--serial", default="")
    parser.add_argument("--descendant-post", required=True)
    parser.add_argument("--uninstall", required=True)
    parser.add_argument("--teardown", required=True)
    if seal_file:
        parser.add_argument("--seal-file", default="")
        parser.add_argument("--seal-digest", default="")
        parser.add_argument("--seal-json", default="")
    else:
        parser.add_argument("--seal-json", required=True)
        parser.add_argument("--seal-file", default="")
        parser.add_argument("--seal-digest", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stranger-host operator commands")
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight")
    preflight.add_argument("--root", default="/")
    preflight.add_argument("--image-name", default="")
    preflight.add_argument("--image-source", default="operator-attestation")
    preflight.add_argument("--allow-metadata", action="store_true")
    preflight.add_argument("--cgroup-fstype", default=None)
    preflight.add_argument("--out", default="")
    preflight.set_defaults(func=command_preflight)

    boot = commands.add_parser("capture-boot")
    boot.add_argument("--root", default="/")
    boot.add_argument("--serial-file", required=True)
    boot.add_argument("--out", required=True)
    boot.add_argument("--serial-out", default="")
    boot.set_defaults(func=command_capture_boot)

    uninstall = commands.add_parser("capture-uninstall")
    uninstall.add_argument("--uninstall-out", required=True)
    uninstall.add_argument("--bpftool-file", default="")
    uninstall.add_argument("--pins-file", default="")
    uninstall.add_argument("--live", action="store_true")
    uninstall.add_argument("--fail-reason", action="append", default=[])
    uninstall.add_argument("--out", required=True)
    uninstall.set_defaults(func=command_capture_uninstall)

    grade = commands.add_parser("grade")
    _add_evidence(grade, seal_file=False)
    grade.set_defaults(func=command_grade)

    built = commands.add_parser("assemble")
    built.add_argument("--out", required=True)
    built.add_argument("--claim", choices=(CLAIM_FIXTURE, CLAIM_AWAITING), required=True)
    built.add_argument("--created-utc", default="")
    _add_evidence(built, seal_file=True)
    built.set_defaults(func=command_assemble)

    sign = commands.add_parser("sign")
    sign.add_argument("--bundle", required=True)
    sign.add_argument("--key", required=True)
    sign.add_argument("--trust", required=True)
    sign.add_argument("--claim", choices=(CLAIM_FIXTURE, CLAIM_AWAITING), required=True)
    sign.set_defaults(func=command_sign)

    verify = commands.add_parser("verify")
    verify.add_argument("--bundle", required=True)
    verify.set_defaults(func=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
