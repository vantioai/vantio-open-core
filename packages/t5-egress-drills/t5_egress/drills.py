"""Named clean-host drills. Each one returns pass or fail with case rows."""

from __future__ import annotations

import os
import socket
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from t5_egress.decide import decide_dns_query, decide_dns_response, decide_get, decide_icmp, decide_loopback
from t5_egress.decision import allow, deny_eval
from t5_egress.evidence import evidence_record, sha256_hex
from t5_egress.fixtures import dns_ns_response, dns_query, icmp_message, ipv4_icmp, ipv6_icmp
from t5_egress.net_setup import add_ipv4, bring_up_lo
from t5_egress.policy import Policy
from t5_egress.symlink import open_workload_root, read_beneath
from t5_egress.volume import VolumeGate

HIGH = "qmzjxkwpvnrtyshl.allowed.example"
LOW = ("a" * 16) + ".allowed.example"
LISTED = "api.allowed.example"
UNLISTED = "api.other.example"


class CaseLog:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def add(
        self,
        name: str,
        decision: object,
        peer_received: bool,
        expect_action: str,
        expect_peer: bool,
        blob: bytes = b"",
    ) -> None:
        action = getattr(decision, "action")
        row: dict[str, object] = {
            "name": name,
            "action": action,
            "reason": getattr(decision, "reason"),
            "transmit": getattr(decision, "transmit"),
            "evaluation_failure": getattr(decision, "evaluation_failure"),
            "peer_received": peer_received,
            "expect_action": expect_action,
            "expect_peer": expect_peer,
            "ok": action == expect_action and peer_received is expect_peer,
        }
        if blob:
            row["packet_sha256"] = sha256_hex(blob)
        self.rows.append(row)

    def ok(self) -> bool:
        return bool(self.rows) and all(bool(row["ok"]) for row in self.rows)


def finish(drill_id: str, log: CaseLog, **extra: object) -> dict[str, object]:
    return evidence_record(drill_id, "pass" if log.ok() else "fail", log.rows, **extra)


def _udp(bind: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    sock.settimeout(0.4)
    return sock


def _recv(sock: socket.socket) -> bool:
    try:
        sock.recvfrom(4096)
        return True
    except socket.timeout:
        return False


def _dns_exchange(packet: bytes, resolver: str, port: int, decision_transmit: bool, upstream: socket.socket) -> bool:
    if not decision_transmit:
        return _recv(upstream)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sender.sendto(packet, (resolver, port))
    finally:
        sender.close()
    return _recv(upstream)


def _prepare_net(addresses: tuple[str, ...]) -> None:
    bring_up_lo()
    for address in addresses:
        add_ipv4(address)


def drill_dns_allow_list(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1",))
    upstream = _udp("127.0.0.1", 5353)
    gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
    log = CaseLog()
    try:
        for mode, action in (("observe", "ALLOW"), ("enforce", "ALLOW")):
            packet = dns_query(LISTED)
            decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
            peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
            log.add(f"listed_{mode}", decision, peer, action, True, packet)
        for mode, action, expect_peer in (
            ("observe", "OBSERVE_WOULD_DENY", True),
            ("enforce", "DENY", False),
        ):
            packet = dns_query(UNLISTED)
            decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
            peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
            log.add(f"unlisted_{mode}", decision, peer, action, expect_peer, packet)
    finally:
        upstream.close()
    return finish("t5-dns-allow-list", log, netns=True)


def drill_dns_long_label(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1",))
    upstream = _udp("127.0.0.1", 5353)
    gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
    log = CaseLog()
    long_name = ("b" * 33) + ".allowed.example"
    split = ("c" * 11) + "." + ("d" * 11) + "." + ("e" * 11) + ".allowed.example"
    try:
        for label, name in (("long", long_name), ("split", split)):
            for mode, action, expect_peer in (
                ("observe", "OBSERVE_WOULD_DENY", True),
                ("enforce", "DENY", False),
            ):
                packet = dns_query(name)
                decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
                peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
                log.add(f"{label}_{mode}", decision, peer, action, expect_peer)
        packet = dns_query(LISTED)
        decision = decide_dns_query(packet, "127.0.0.1", policy, "enforce", True, gate)
        peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
        log.add("listed_enforce", decision, peer, "ALLOW", True, packet)
    finally:
        upstream.close()
    return finish("t5-dns-long-label", log, netns=True)


def drill_dns_high_entropy(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1",))
    upstream = _udp("127.0.0.1", 5353)
    gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
    log = CaseLog()
    try:
        for mode, action, expect_peer in (
            ("observe", "OBSERVE_WOULD_DENY", True),
            ("enforce", "DENY", False),
        ):
            packet = dns_query(HIGH)
            decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
            peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
            log.add(f"high_{mode}", decision, peer, action, expect_peer)
        packet = dns_query(LOW)
        decision = decide_dns_query(packet, "127.0.0.1", policy, "enforce", True, gate)
        peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
        log.add("low_enforce", decision, peer, "ALLOW", True, packet)
    finally:
        upstream.close()
    return finish("t5-dns-high-entropy", log, netns=True)


def _volume_pass(policy: Policy, mode: str, upstream: socket.socket, gate: VolumeGate, log: CaseLog) -> None:
    cap = policy.dns.max_queries
    for index in range(cap):
        packet = dns_query(LISTED, qid=index + 1)
        decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
        peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
        log.add(f"{mode}_within_{index}", decision, peer, "ALLOW", True)
    packet = dns_query(LISTED, qid=cap + 1)
    decision = decide_dns_query(packet, "127.0.0.1", policy, mode, True, gate)
    expect = "OBSERVE_WOULD_DENY" if mode == "observe" else "DENY"
    peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
    log.add(f"{mode}_over", decision, peer, expect, mode == "observe", packet)


def drill_dns_query_volume(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1",))
    upstream = _udp("127.0.0.1", 5353)
    log = CaseLog()
    try:
        observe_gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
        _volume_pass(policy, "observe", upstream, observe_gate, log)
        time.sleep(policy.dns.window_seconds + 0.25)
        packet = dns_query(LISTED, qid=900)
        decision = decide_dns_query(packet, "127.0.0.1", policy, "enforce", True, observe_gate)
        peer = _dns_exchange(packet, "127.0.0.1", 5353, decision.transmit, upstream)
        log.add("after_window", decision, peer, "ALLOW", True, packet)
        enforce_gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
        _volume_pass(policy, "enforce", upstream, enforce_gate, log)
    finally:
        upstream.close()
    return finish("t5-dns-query-volume", log, netns=True)


def drill_dns_unknown_delegation(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1", "198.51.100.8"))
    listed = _udp("127.0.0.1", 5353)
    unknown = _udp("198.51.100.8", 53)
    gate = VolumeGate(policy.dns.max_queries, policy.dns.window_seconds, "workload")
    log = CaseLog()
    try:
        response = dns_ns_response("allowed.example", "ns.allowed.example", "198.51.100.8")
        decision = decide_dns_response(response, policy, "enforce", True)
        log.add("response_unknown", decision, False, "DENY", False, response)
        follow = dns_query(LISTED)
        follow_decision = decide_dns_query(follow, "198.51.100.8", policy, "enforce", True, gate)
        peer = _dns_exchange(follow, "198.51.100.8", 53, follow_decision.transmit, unknown)
        log.add("follow_unknown", follow_decision, peer, "DENY", False, follow)
        listed_packet = dns_query(LISTED, qid=2)
        listed_decision = decide_dns_query(listed_packet, "127.0.0.1", policy, "enforce", True, gate)
        listed_peer = _dns_exchange(listed_packet, "127.0.0.1", 5353, listed_decision.transmit, listed)
        log.add("follow_listed", listed_decision, listed_peer, "ALLOW", True, listed_packet)
    finally:
        listed.close()
        unknown.close()
    return finish("t5-dns-unknown-delegation", log, netns=True)


def _icmp_seen(listener: socket.socket, kind: int, ident: int) -> bool:
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        listener.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            data, _addr = listener.recvfrom(4096)
        except socket.timeout:
            return False
        if len(data) < 20:
            continue
        header_len = (data[0] & 0x0F) * 4
        if len(data) < header_len + 6 or data[9] != 1:
            continue
        got_kind = data[header_len]
        got_ident = struct.unpack_from(">H", data, header_len + 4)[0]
        if got_kind == kind and got_ident == ident:
            return True
    return False


def _icmp_exchange(payload: bytes, dest: str, kind: int, ident: int, decision_transmit: bool, listener: socket.socket) -> bool:
    if decision_transmit:
        sender = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        try:
            sender.sendto(payload, (dest, 0))
        finally:
            sender.close()
    return _icmp_seen(listener, kind, ident)


def drill_icmp_egress(policy: Policy) -> dict[str, object]:
    _prepare_net(("198.51.100.9", "198.51.100.10", "169.254.169.254"))
    allowed_listener = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    other_listener = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    link_listener = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    allowed_listener.bind(("198.51.100.9", 0))
    other_listener.bind(("198.51.100.10", 0))
    link_listener.bind(("169.254.169.254", 0))
    for sock in (allowed_listener, other_listener, link_listener):
        sock.settimeout(0.4)
    log = CaseLog()
    try:
        echo = icmp_message(8, ident=21)
        packet = ipv4_icmp("198.51.100.1", "198.51.100.9", echo)
        for mode, action in (("observe", "ALLOW"), ("enforce", "ALLOW")):
            decision = decide_icmp(packet, policy, mode, True)
            peer = _icmp_exchange(echo, "198.51.100.9", 8, 21, decision.transmit, allowed_listener)
            log.add(f"echo_listed_{mode}", decision, peer, action, True, packet)
        other = icmp_message(8, ident=22)
        other_packet = ipv4_icmp("198.51.100.1", "198.51.100.10", other)
        for mode, action, expect_peer in (("observe", "OBSERVE_WOULD_DENY", True), ("enforce", "DENY", False)):
            decision = decide_icmp(other_packet, policy, mode, True)
            peer = _icmp_exchange(other, "198.51.100.10", 8, 22, decision.transmit, other_listener)
            log.add(f"echo_other_{mode}", decision, peer, action, expect_peer)
        kind = icmp_message(13, ident=23)
        kind_packet = ipv4_icmp("198.51.100.1", "198.51.100.9", kind)
        decision = decide_icmp(kind_packet, policy, "enforce", True)
        peer = _icmp_exchange(kind, "198.51.100.9", 13, 23, decision.transmit, allowed_listener)
        log.add("non_echo_enforce", decision, peer, "DENY", False, kind_packet)
        link = icmp_message(8, ident=24)
        link_packet = ipv4_icmp("198.51.100.1", "169.254.169.254", link)
        decision = decide_icmp(link_packet, policy, "enforce", True)
        peer = _icmp_exchange(link, "169.254.169.254", 8, 24, decision.transmit, link_listener)
        log.add("link_local_enforce", decision, peer, "DENY", False, link_packet)
        v6 = ipv6_icmp((0, 0, 0, 0, 0, 0, 0, 1), 128)
        v6_decision = decide_icmp(v6, policy, "enforce", True)
        log.add("icmpv6_enforce", v6_decision, False, "DENY", False, v6)
    finally:
        allowed_listener.close()
        other_listener.close()
        link_listener.close()
    return finish("t5-icmp-egress", log, netns=True)


def _tcp_server(host: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    if family == socket.AF_INET6:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(8)
    sock.settimeout(0.4)
    return sock


def _tcp_hit(server: socket.socket, host: str, port: int, transmit: bool) -> bool:
    if transmit:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        client = socket.socket(family, socket.SOCK_STREAM)
        client.settimeout(0.4)
        try:
            client.connect((host, port))
            client.sendall(b"t5")
        finally:
            client.close()
    try:
        conn, _addr = server.accept()
    except socket.timeout:
        return False
    conn.close()
    return True


def _one_get(policy: Policy, mode: str, host: str, path: str, query: str, body: bytes, dest: str, port: int, server: socket.socket, log: CaseLog, name: str, expect_action: str, expect_peer: bool) -> None:
    header = f"GET {path if not query else path + '?' + query} HTTP/1.0\r\nHost: {host}\r\nAccept: */*\r\n"
    if body:
        header += f"Content-Length: {len(body)}\r\n"
    header += "\r\n"
    raw = header.encode("ascii") + body
    decision = decide_get(
        True,
        "GET",
        host,
        path,
        query,
        len(body),
        len(header.encode("ascii")),
        policy,
        mode,
        True,
        connected_address=dest,
    )
    peer = False
    if decision.transmit:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(0.4)
        try:
            client.connect((dest, port))
            client.sendall(raw)
        finally:
            client.close()
    try:
        conn, _addr = server.accept()
        peer = True
        conn.close()
    except socket.timeout:
        peer = False
    log.add(name, decision, peer, expect_action, expect_peer, raw)


def drill_get_write(policy: Policy) -> dict[str, object]:
    _prepare_net(("198.51.100.10",))
    server = _tcp_server("198.51.100.10", 8080)
    log = CaseLog()
    try:
        for mode, action in (("observe", "ALLOW"), ("enforce", "ALLOW")):
            _one_get(policy, mode, "allowed.example", "/v1/models", "limit=10", b"", "198.51.100.10", 8080, server, log, f"benign_{mode}", action, True)
        for mode, action, expect_peer in (("observe", "OBSERVE_WOULD_DENY", True), ("enforce", "DENY", False)):
            _one_get(
                policy,
                mode,
                "allowed.example",
                "/v1/models",
                "limit=10",
                b"write",
                "198.51.100.10",
                8080,
                server,
                log,
                f"body_{mode}",
                action,
                expect_peer,
            )
        _one_get(policy, "enforce", "allowed.example", "/v1/models", "data=1", b"", "198.51.100.10", 8080, server, log, "query_key_enforce", "DENY", False)
        _one_get(policy, "enforce", "allowed.example", "/upload/x", "", b"", "198.51.100.10", 8080, server, log, "write_path_enforce", "DENY", False)
        _one_get(policy, "enforce", "allowed.example", "/v1/models", "n=" + ("a" * 200), b"", "198.51.100.10", 8080, server, log, "long_query_enforce", "DENY", False)
        for host in ("127.0.0.1", "0.0.0.0"):
            decision = decide_get(True, "GET", host, "/v1/models", "", 0, 20, policy, "enforce", True)
            log.add(f"loopback_{host}", decision, False, "NOT_IN_SCOPE", False)
    finally:
        server.close()
    return finish("t5-get-write", log, netns=True)


def drill_loopback(policy: Policy) -> dict[str, object]:
    _prepare_net(("127.0.0.1",))
    allowed = _tcp_server("127.0.0.1", 18080)
    privileged = _tcp_server("127.0.0.1", 22)
    wildcard = _tcp_server("0.0.0.0", 2375)
    udp_allowed = _udp("127.0.0.1", 18080)
    udp_priv = _udp("127.0.0.1", 53)
    log = CaseLog()
    try:
        for mode, action in (("observe", "ALLOW"), ("enforce", "ALLOW")):
            decision = decide_loopback("127.0.0.1", 18080, "tcp", policy, mode, True)
            peer = _tcp_hit(allowed, "127.0.0.1", 18080, decision.transmit)
            log.add(f"allowed_tcp_{mode}", decision, peer, action, True)
        for dest, port, server, label in (
            ("127.0.0.1", 22, privileged, "port_22"),
            ("0.0.0.0", 2375, wildcard, "wildcard_2375"),
        ):
            decision = decide_loopback(dest, port, "tcp", policy, "enforce", True)
            peer = _tcp_hit(server, dest, port, decision.transmit)
            log.add(label, decision, peer, "DENY", False)
        mapped = decide_loopback("::ffff:127.0.0.1", 22, "tcp", policy, "observe", True)
        mapped_peer = _tcp_hit(privileged, "::ffff:127.0.0.1", 22, mapped.transmit)
        log.add("mapped_observe", mapped, mapped_peer, "OBSERVE_WOULD_DENY", True)
        udp_ok = decide_loopback("127.0.0.1", 18080, "udp", policy, "enforce", True)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            if udp_ok.transmit:
                sender.sendto(b"t5", ("127.0.0.1", 18080))
        finally:
            sender.close()
        log.add("udp_allowed", udp_ok, _recv(udp_allowed), "ALLOW", True)
        udp_bad = decide_loopback("127.0.0.1", 53, "udp", policy, "enforce", True)
        log.add("udp_privileged", udp_bad, _recv(udp_priv), "DENY", False)
    finally:
        for sock in (allowed, privileged, wildcard, udp_allowed, udp_priv):
            sock.close()
    return finish("t5-loopback-priv-esc", log, netns=True)


def _symlink_cases(root: str) -> CaseLog:
    log = CaseLog()
    outside = tempfile.mkdtemp(prefix="t5-out-")
    sentinel = Path(outside) / "secret"
    sentinel.write_text("SENTINEL-OUTSIDE", encoding="utf-8")
    note = Path(root) / "note"
    note.write_text("inside", encoding="utf-8")
    os.symlink("note", Path(root) / "inner")
    os.symlink(sentinel, Path(root) / "escape")
    os.mkdir(Path(root) / "sub")
    os.symlink(outside, Path(root) / "outdir")
    root_fd = open_workload_root(root)
    if not isinstance(root_fd, int):
        log.add("root", root_fd, False, "ALLOW", False)
        return log
    try:
        decision, data = read_beneath(root_fd, "note")
        log.add("inside_file", decision if data == b"inside" else deny_eval("open_failed"), data == b"inside", "ALLOW", True)
        inner, inner_data = read_beneath(root_fd, "inner")
        log.add("inner_symlink", inner if inner_data == b"inside" else deny_eval("open_failed"), inner_data == b"inside", "ALLOW", True)
        escaped, escaped_data = read_beneath(root_fd, "escape")
        log.add("escape", allow() if escaped_data else escaped, bool(escaped_data), "DENY", False)
        via, via_data = read_beneath(root_fd, "outdir/secret")
        log.add("dir_symlink", allow() if via_data else via, bool(via_data), "DENY", False)
        dotted, dotted_data = read_beneath(root_fd, "../" + os.path.basename(outside) + "/secret")
        log.add("dotdot", allow() if dotted_data else dotted, bool(dotted_data), "DENY", False)
    finally:
        os.close(root_fd)
    linked_parent = tempfile.mkdtemp(prefix="t5-link-")
    linked = Path(linked_parent) / "root"
    os.symlink(root, linked)
    root_decision = open_workload_root(str(linked))
    log.add("symlink_root", root_decision, False, "DENY", False)
    race_root = open_workload_root(root)
    if isinstance(race_root, int):
        flip_path = Path(root) / "flip"
        flip_path.write_bytes(b"inside")
        stop = threading.Event()

        def flip() -> None:
            while not stop.is_set():
                try:
                    flip_path.unlink()
                except FileNotFoundError:
                    pass
                try:
                    os.symlink(sentinel, flip_path)
                except FileExistsError:
                    continue
                try:
                    flip_path.unlink()
                except FileNotFoundError:
                    pass
                try:
                    fd = os.open(flip_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    continue
                os.write(fd, b"inside")
                os.close(fd)

        thread = threading.Thread(target=flip)
        thread.start()
        saw_sentinel = False
        try:
            for _ in range(40):
                _decision, data = read_beneath(race_root, "flip")
                if b"SENTINEL-OUTSIDE" in data:
                    saw_sentinel = True
                    break
        finally:
            stop.set()
            thread.join()
            os.close(race_root)
        log.add("race", allow() if saw_sentinel else deny_eval("symlink_escape"), False, "DENY", False)
    magic_fd = os.open(sentinel, os.O_RDONLY)
    try:
        os.symlink(f"/proc/self/fd/{magic_fd}", Path(root) / "magic")
        magic_root = open_workload_root(root)
        if isinstance(magic_root, int):
            try:
                _decision, data = read_beneath(magic_root, "magic")
                log.add("magic_link", allow() if b"SENTINEL-OUTSIDE" in data else deny_eval("symlink_escape"), False, "DENY", False)
            finally:
                os.close(magic_root)
    finally:
        os.close(magic_fd)
    return log


def drill_symlink_escape() -> dict[str, object]:
    root = tempfile.mkdtemp(prefix="t5-root-")
    log = _symlink_cases(root)
    outside = tempfile.mkdtemp(prefix="t5-bind-")
    (Path(outside) / "secret").write_text("SENTINEL-OUTSIDE", encoding="utf-8")
    mount_point = Path(root) / "bound"
    mount_point.mkdir(exist_ok=True)
    try:
        subprocess.check_call(["mount", "--bind", outside, str(mount_point)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        failed = evidence_record("t5-symlink-escape", "fail", log.rows, netns=False, mount_ns=False)
        return failed
    root_fd = open_workload_root(root)
    try:
        if isinstance(root_fd, int):
            decision, data = read_beneath(root_fd, "bound/secret")
            log.add("bind_mount", allow() if data else decision, bool(data), "DENY", False)
        else:
            log.add("bind_mount", root_fd, False, "DENY", True)
    finally:
        if isinstance(root_fd, int):
            os.close(root_fd)
        subprocess.call(["umount", str(mount_point)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return finish("t5-symlink-escape", log, netns=False, mount_ns=True)


DRILLS = {
    "t5-dns-allow-list": drill_dns_allow_list,
    "t5-dns-long-label": drill_dns_long_label,
    "t5-dns-high-entropy": drill_dns_high_entropy,
    "t5-dns-query-volume": drill_dns_query_volume,
    "t5-dns-unknown-delegation": drill_dns_unknown_delegation,
    "t5-icmp-egress": drill_icmp_egress,
    "t5-get-write": drill_get_write,
    "t5-loopback-priv-esc": drill_loopback,
    "t5-symlink-escape": drill_symlink_escape,
}
