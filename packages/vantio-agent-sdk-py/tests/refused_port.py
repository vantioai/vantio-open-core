"""A localhost port that stays connection-refused for the whole test."""

from __future__ import annotations

import socket


class RefusedPort:
    """Reserve 127.0.0.1 and do not listen.

    Binding port 0 and then closing the socket returns that port to the
    ephemeral pool. On a busy runner another process can bind it and answer
    HTTP before the client connects, so the client succeeds instead of seeing
    connection refused. This socket stays bound and does not listen, which
    keeps the port and makes connect return ECONNREFUSED until close().
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self.port = int(self._sock.getsockname()[1])

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> RefusedPort:
        return self

    def __exit__(self, *_exc: object) -> bool:
        self.close()
        return False
