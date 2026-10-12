"""Offline GCP delivery entry.

The implementation is split across offline_deliver_N.py so each blob stays
small enough to publish. Importing this module loads those parts into this
namespace. Tests and the workflow both use this name.
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _name in (
    "offline_deliver_1.py",
    "offline_deliver_2.py",
    "offline_deliver_3.py",
):
    _path = _HERE / _name
    exec(compile(_path.read_text(encoding="utf-8"), str(_path), "exec"), globals())

if __name__ == "__main__":
    sys.exit(main())
