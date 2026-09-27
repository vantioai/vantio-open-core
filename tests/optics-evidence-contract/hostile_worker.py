"""Isolated hostile-object worker. The parent owns the timeout."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "packages" / "optics-evidence-contract" / "src"
sys.path.insert(0, str(SRC))

import validate  # noqa: E402


class _Hanging:
    calls = 0

    @property
    def boom(self):
        _Hanging.calls += 1
        while True:
            # External timeout owns this process. The validator must not reach this property.
            pass


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "hang":
        _Hanging().boom
        return
    if mode == "validate":
        result = validate.validate_evidence(_Hanging())
        sys.stdout.write("CALLS " + str(_Hanging.calls) + "\n")
        sys.stdout.write(validate.canonical_json(result))
        return
    sys.stderr.write("usage: hostile_worker.py validate|hang\n")
    sys.exit(2)


if __name__ == "__main__":
    main()
