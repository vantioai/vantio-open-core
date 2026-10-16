"""Test path setup and a small valid policy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY = {
    "dns": {
        "allowed_names": ["allowed.example"],
        "allowed_resolvers": ["127.0.0.1"],
        "max_label_length": 32,
        "entropy_min_length": 12,
        "entropy_bits_max": 3.5,
        "max_queries": 30,
        "window_seconds": 10,
    },
    "icmp": {
        "allowed_destinations": ["198.51.100.9"],
        "allowed_types": [0, 8],
    },
    "http_get": {
        "allowed_hosts": ["allowed.example"],
        "max_query_length": 128,
        "max_path_length": 256,
        "max_header_bytes": 1024,
        "write_query_keys": ["data", "payload", "cmd", "exec", "file", "upload", "content"],
        "write_path_prefixes": ["/upload", "/exec", "/write", "/v1/files"],
    },
    "loopback": {
        "allowed_ports": [18080],
        "privileged_ports": [22, 2375, 2376, 6443, 10250, 10255, 5001],
    },
}
