"""Seal a customer wheel and sdist of vantio-install.

The source pin stays ``0.1.0-stage-a``. That string is not a PEP 440 version,
and hatchling will not build the tree as it sits. This script copies the
package, sets ``project.version`` on the copy to ``0.1.0+stage.a``, and runs
``python -m build`` there.

It does not upload the artifacts, and it does not rewrite the source pin or
the frozen Optics package versions.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_VERSION = "0.1.0-stage-a"
SEAL_VERSION = "0.1.0+stage.a"
_VERSION_LINE = f'version = "{SOURCE_VERSION}"'
_SEAL_LINE = f'version = "{SEAL_VERSION}"'
_FROZEN_PUBLIC = ("0.3.24", "0.2.4", "3.1.0")
_SKIP_DIRS = {"__pycache__", "dist", ".pytest_cache", ".mypy_cache", "build"}


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def seal_version_text(pyproject: str) -> str:
    """Return pyproject text whose project version is the PEP 440 seal version."""
    if pyproject.count(_VERSION_LINE) != 1:
        raise ValueError("expected exactly one source version pin")
    return pyproject.replace(_VERSION_LINE, _SEAL_LINE, 1)


def source_pin_intact(root: Path) -> None:
    """Raise if the source identity or a frozen public pin moved."""
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    if _VERSION_LINE not in pyproject:
        raise ValueError("source version pin moved")
    if _SEAL_LINE in pyproject:
        raise ValueError("seal version was written into the source tree")
    init_text = (root / "vantio_install" / "__init__.py").read_text(encoding="utf-8")
    constants_text = (root / "vantio_install" / "constants.py").read_text(encoding="utf-8")
    if SOURCE_VERSION not in init_text or f'INSTALLER_VERSION = "{SOURCE_VERSION}"' not in constants_text:
        raise ValueError("installer identity moved")
    for pin in _FROZEN_PUBLIC:
        if pin not in constants_text:
            raise ValueError(f"frozen public pin {pin} missing")


def _ignore(directory: str, names: list[str]) -> set[str]:
    del directory
    return {name for name in names if name in _SKIP_DIRS or name.endswith(".pyc")}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seal(outdir: Path) -> list[Path]:
    """Build the sealed wheel and sdist into ``outdir`` and write SHA256SUMS."""
    root = package_root()
    source_pin_intact(root)
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vantio-install-seal-") as tmp:
        copy = Path(tmp) / "vantio-install"
        shutil.copytree(root, copy, ignore=_ignore)
        pyproject_path = copy / "pyproject.toml"
        pyproject_path.write_text(seal_version_text(pyproject_path.read_text(encoding="utf-8")), encoding="utf-8")
        source_pin_intact(root)
        completed = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(outdir)],
            cwd=copy,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise RuntimeError("python -m build failed")
    artifacts = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    if not any(path.suffix == ".whl" or path.name.endswith(".whl") for path in artifacts):
        wheels = [path.name for path in artifacts]
        raise RuntimeError(f"no wheel in {outdir}: {wheels}")
    lines = [f"{_sha256(path)}  {path.name}" for path in artifacts]
    (outdir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    source_pin_intact(root)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seal_customer_artifact")
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        artifacts = seal(args.outdir)
    except (OSError, RuntimeError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    for path in artifacts:
        sys.stdout.write(f"{path}\n")
    sys.stdout.write(f"{args.outdir / 'SHA256SUMS'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
