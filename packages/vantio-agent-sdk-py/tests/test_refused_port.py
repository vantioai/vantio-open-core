"""The refused-port helper must stay refused and unstealable while held."""

from __future__ import annotations

import errno
import socket
import unittest

from .refused_port import RefusedPort


class RefusedPortTests(unittest.TestCase):
    def test_held_port_refuses_and_cannot_be_bound(self) -> None:
        with RefusedPort() as refused:
            other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(OSError) as caught:
                    other.bind(("127.0.0.1", refused.port))
            finally:
                other.close()
            self.assertEqual(caught.exception.errno, errno.EADDRINUSE)
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(ConnectionRefusedError):
                    client.connect(("127.0.0.1", refused.port))
            finally:
                client.close()

    def test_closed_port_can_be_bound(self) -> None:
        refused = RefusedPort()
        port = refused.port
        refused.close()
        other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            other.bind(("127.0.0.1", port))
            self.assertEqual(other.getsockname()[1], port)
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
