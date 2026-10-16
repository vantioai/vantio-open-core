"""Lab payload. Holds sockets. Does not print secrets or prompts."""

import ctypes
import os
import socket
import sys
import time

_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
_LIBC.prctl.restype = ctypes.c_int
_PR_SET_DUMPABLE = 4


def set_comm(name: str) -> None:
    fd = os.open("/proc/self/comm", os.O_WRONLY)
    try:
        os.write(fd, name.encode()[:15])
    finally:
        os.close(fd)


def hold(ip: str, port: int) -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ip, port))
    server.listen(1)
    client = socket.socket()
    client.connect((ip, port))
    accepted, _peer = server.accept()
    # Keep the accepted socket. Dropping it closes the connection.
    globals()["_held"] = (server, client, accepted)


def listen_only(ip: str, port: int) -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ip, port))
    server.listen(1)
    globals()["_listen"] = server


def drop_uid() -> None:
    uid = int(os.environ.get("VANTIO_LAB_UID", "0"))
    if uid == 0:
        return
    os.setgid(uid)
    os.setuid(uid)
    # setuid clears the dumpable bit, which hides exe, fds, and environ from
    # the same uid. The lab scanner is that uid and must be able to read them.
    if _LIBC.prctl(_PR_SET_DUMPABLE, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl")


def ready(path: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, b"up\n")
    finally:
        os.close(fd)


def main() -> None:
    role = sys.argv[1]
    ready_path = sys.argv[2]
    if role == "agent":
        set_comm("python3")
        hold("10.88.0.2", 8443)
        hold_extra("10.88.0.9", 8443)
        hold_extra("10.88.1.1", 9)
        drop_uid()
        ready(ready_path)
    elif role == "ollama":
        set_comm("ollama")
        listen_only("127.0.0.1", 11434)
        drop_uid()
        ready(ready_path)
    elif role == "mcp":
        set_comm("mcp-server-filesystem")
        drop_uid()
        ready(ready_path)
    elif role == "lineage":
        set_comm("claude")
        child = os.fork()
        if child == 0:
            set_comm("python3")
            hold("10.88.0.8", 8443)
            drop_uid()
            ready(ready_path)
            time.sleep(600)
            return
        drop_uid()
        time.sleep(600)
        return
    elif role == "unknown":
        set_comm("python3")
        drop_uid()
        ready(ready_path)
    elif role == "partial":
        set_comm("claude")
        ready(ready_path)
    elif role == "decoy-web":
        set_comm("python3")
        listen_only("127.0.0.1", 8080)
        drop_uid()
        ready(ready_path)
    elif role == "decoy-file":
        set_comm("sleep")
        drop_uid()
        ready(ready_path)
    elif role == "decoy-curl":
        set_comm("curl")
        drop_uid()
        ready(ready_path)
    elif role == "decoy-mcp":
        set_comm("sleep")
        drop_uid()
        ready(ready_path)
    else:
        raise SystemExit(2)
    time.sleep(600)


def hold_extra(ip: str, port: int) -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ip, port))
    server.listen(1)
    client = socket.socket()
    client.connect((ip, port))
    accepted, _peer = server.accept()
    held = globals().setdefault("_extra", [])
    held.append((server, client, accepted))


if __name__ == "__main__":
    main()
