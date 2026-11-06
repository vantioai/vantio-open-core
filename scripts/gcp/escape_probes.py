#!/usr/bin/env python3
"""Try enrolled-cgroup escapes and print one line per probe.

A connect that succeeds is ok. A timeout or errno 1 is denied. A probe that
does not run is ok, so the grade fails closed. This file does not detach
the loader.
"""

from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
from pathlib import Path

AT_EMPTY_PATH = 0x1000
CLONE_NEWUSER = 0x10000000
EXECVEAT = 322
MEMFD_CREATE = 319


def _result(kind: str, errno: int) -> str:
    return f"{kind} {errno}"


def _connect(ip: str, port: int) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect((ip, port))
    except socket.timeout:
        return _result("denied", 0)
    except OSError as exc:
        if exc.errno == 1:
            return _result("denied", 1)
        return _result("ok", exc.errno or 0)
    else:
        return _result("ok", 0)
    finally:
        sock.close()


def _join(cgroup: str) -> None:
    Path(cgroup, "cgroup.procs").write_text(str(os.getpid()))


def _read_child(pid: int, read_fd: int) -> str:
    os.waitpid(pid, 0)
    data = os.read(read_fd, 64).decode("ascii", errors="replace").strip().split()
    if len(data) != 2:
        return _result("ok", 0)
    return _result(data[0], int(data[1]))


def _fork_result(cgroup: str, fn) -> str:
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            _join(cgroup)
            text = fn()
        except OSError:
            text = _result("ok", 0)
        os.write(write_fd, (text + "\n").encode())
        os._exit(0)
    os.close(write_fd)
    return _read_child(pid, read_fd)


def _exec_code(ip: str, port: int, result: Path) -> str:
    return (
        "import socket\n"
        f"s=socket.socket(); s.settimeout(1.5)\n"
        "try:\n"
        f"    s.connect(({ip!r}, {port}))\n"
        f"    open({str(result)!r}, 'w').write('ok 0\\n')\n"
        "except socket.timeout:\n"
        f"    open({str(result)!r}, 'w').write('denied 0\\n')\n"
        "except OSError as exc:\n"
        "    kind = 'denied' if exc.errno == 1 else 'ok'\n"
        f"    open({str(result)!r}, 'w').write(f'{{kind}} {{exc.errno or 0}}\\n')\n"
    )


def _exec_probe(cgroup: str, ip: str, port: int, out: Path, script: Path | None) -> str:
    result = out / "escape-result.txt"
    result.unlink(missing_ok=True)
    code = _exec_code(ip, port, result)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            _join(cgroup)
            if script is None:
                os.execv(sys.executable, [sys.executable, "-c", code])
            else:
                script.write_text(code, encoding="utf-8")
                os.execv(sys.executable, [sys.executable, str(script)])
        except OSError:
            os.write(write_fd, b"ok 0\n")
        os._exit(0)
    os.close(write_fd)
    os.waitpid(pid, 0)
    if not result.is_file():
        return _result("ok", 0)
    parts = result.read_text(encoding="utf-8").split()
    if len(parts) != 2:
        return _result("ok", 0)
    return _result(parts[0], int(parts[1]))


def _memfd_probe(cgroup: str, ip: str, port: int, out: Path) -> str:
    result = out / "escape-memfd.txt"
    result.unlink(missing_ok=True)
    code = _exec_code(ip, port, result)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long

    def child() -> str:
        _join(cgroup)
        blob = Path(sys.executable).read_bytes()
        fd = libc.syscall(MEMFD_CREATE, b"vantio-escape", 0)
        if fd < 0:
            return _result("ok", ctypes.get_errno())
        os.write(fd, blob)
        os.lseek(fd, 0, os.SEEK_SET)
        argv = (ctypes.c_char_p * 4)(sys.executable.encode(), b"-c", code.encode(), None)
        env_items = [f"{key}={value}".encode() for key, value in os.environ.items()]
        env = (ctypes.c_char_p * (len(env_items) + 1))(*env_items, None)
        libc.syscall(EXECVEAT, ctypes.c_int(fd), b"", argv, env, AT_EMPTY_PATH)
        return _result("ok", ctypes.get_errno())

    text = _fork_result(cgroup, child)
    if result.is_file():
        parts = result.read_text(encoding="utf-8").split()
        if len(parts) == 2:
            return _result(parts[0], int(parts[1]))
    return text


def _static_probe(cgroup: str, ip: str, port: int, out: Path) -> str:
    source = out / "static-connect.c"
    binary = out / "static-connect"
    source.write_text(
        "#include <errno.h>\n"
        "#include <fcntl.h>\n"
        "#include <netinet/in.h>\n"
        "#include <arpa/inet.h>\n"
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        "#include <sys/socket.h>\n"
        "#include <sys/time.h>\n"
        "#include <unistd.h>\n"
        "int main(void) {\n"
        f"  const char *path = {json_string(str(out / 'escape-static.txt'))};\n"
        "  int fd = socket(AF_INET, SOCK_STREAM, 0);\n"
        "  struct timeval tv = {1, 500000};\n"
        "  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);\n"
        "  setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);\n"
        "  struct sockaddr_in addr;\n"
        "  memset(&addr, 0, sizeof addr);\n"
        "  addr.sin_family = AF_INET;\n"
        f"  addr.sin_port = htons({port});\n"
        f"  inet_pton(AF_INET, {json_string(ip)}, &addr.sin_addr);\n"
        "  int rc = connect(fd, (struct sockaddr *)&addr, sizeof addr);\n"
        "  FILE *out = fopen(path, \"w\");\n"
        "  if (rc == 0) fprintf(out, \"ok 0\\n\");\n"
        "  else if (errno == 1 || errno == 110 || errno == 11) fprintf(out, \"denied %d\\n\", errno == 1 ? 1 : 0);\n"
        "  else fprintf(out, \"ok %d\\n\", errno);\n"
        "  fclose(out);\n"
        "  return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    built = subprocess.run(
        ["gcc", "-static", "-O2", "-o", str(binary), str(source)],
        capture_output=True,
        check=False,
    )
    if built.returncode != 0 or not binary.is_file():
        return _result("ok", 0)
    result = out / "escape-static.txt"
    result.unlink(missing_ok=True)

    def child() -> str:
        _join(cgroup)
        os.execv(str(binary), [str(binary)])
        return _result("ok", 0)

    text = _fork_result(cgroup, child)
    if result.is_file():
        parts = result.read_text(encoding="utf-8").split()
        if len(parts) == 2:
            return _result(parts[0], int(parts[1]))
    return text


def json_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _userns(cgroup: str, ip: str, port: int) -> str:
    def child() -> str:
        _join(cgroup)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.unshare(CLONE_NEWUSER) != 0:
            return _result("ok", ctypes.get_errno())
        return _connect(ip, port)

    return _fork_result(cgroup, child)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        return 2
    cgroup, ip, port_text, out_text = argv[1:]
    port = int(port_text)
    out = Path(out_text)
    out.mkdir(parents=True, exist_ok=True)
    probes = {
        "interpreter": _fork_result(cgroup, lambda: _connect(ip, port)),
        "exec": _exec_probe(cgroup, ip, port, out, None),
        "file": _exec_probe(cgroup, ip, port, out, out / "escape-file.py"),
        "memfd": _memfd_probe(cgroup, ip, port, out),
        "userns": _userns(cgroup, ip, port),
        "static": _static_probe(cgroup, ip, port, out),
    }
    for name in ("file", "exec", "memfd", "interpreter", "static", "userns"):
        kind, errno = probes[name].split()
        print(f"escape_{name}={kind} errno={errno}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
