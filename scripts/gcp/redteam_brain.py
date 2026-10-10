"""Offline red-team brain handoff. No GCP calls.

The fetch job downloads the pinned weights and llama.cpp build, checks the
hashes, and uploads them to the private lab bucket. The offline VM has no
route to the internet. Gross cost for the largest allowed shape stays under
the one-dollar worst-case run, which is under the five-dollar lab budget.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

MACHINE_USD_PER_HOUR = {
    "e2-micro": Decimal("0.0084"),
    "e2-standard-4": Decimal("0.134014"),
    "e2-standard-8": Decimal("0.268028"),
}
BRAIN_MACHINE = "e2-standard-4"
BRAIN_DISK_GB = Decimal("30")
PD_BALANCED_USD_PER_GB_MONTH = Decimal("0.10")
HOURS_PER_MONTH = Decimal("730")
MAX_LIFE_MINUTES = 120
# Matches lab_auto.WORST_CASE_RUN_USD. spend + this ceiling must stay under $5.
GROSS_RUN_CAP_USD = Decimal("1.00")
LAB_BUDGET_USD = Decimal("5.00")

MODEL_NAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
MODEL_SHA256 = "626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d"
MODEL_BYTES = 2104932768
RUNTIME_NAME = "llama-b11540-bin-ubuntu-x64.tar.gz"
RUNTIME_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11540/llama-b11540-bin-ubuntu-x64.tar.gz"
RUNTIME_SHA256 = "513e4a63818ce3a480570a2b4c7cabb173b06a72b2aa4158fcfaba687462355c"
RUNTIME_BYTES = 17809672


def estimate_gross_usd(machine: str, minutes: int, disk_gb: Decimal = Decimal("10")) -> Decimal:
    if machine not in MACHINE_USD_PER_HOUR:
        raise ValueError("machine_type")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1 or minutes > MAX_LIFE_MINUTES:
        raise ValueError("minutes")
    if disk_gb <= 0 or disk_gb > 30:
        raise ValueError("disk")
    hours = Decimal(minutes) / Decimal(60)
    disk_per_hour = disk_gb * PD_BALANCED_USD_PER_GB_MONTH / HOURS_PER_MONTH
    return (MACHINE_USD_PER_HOUR[machine] + disk_per_hour) * hours


def assert_under_cap(machine: str, minutes: int, disk_gb: Decimal = Decimal("10")) -> Decimal:
    gross = estimate_gross_usd(machine, minutes, disk_gb)
    if gross >= GROSS_RUN_CAP_USD or gross >= LAB_BUDGET_USD:
        raise ValueError("cost")
    return gross


def brain_plan(minutes: int = 90) -> dict[str, str]:
    gross = assert_under_cap(BRAIN_MACHINE, minutes, BRAIN_DISK_GB)
    return {
        "disk_gb": format(BRAIN_DISK_GB, "f"),
        "expected_oop_usd": "0",
        "gross_usd": format(gross.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f"),
        "machine_type": BRAIN_MACHINE,
        "model_sha256": MODEL_SHA256,
        "runtime_sha256": RUNTIME_SHA256,
    }


def hashes_match(model_sha: str, runtime_sha: str) -> bool:
    return model_sha == MODEL_SHA256 and runtime_sha == RUNTIME_SHA256


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(directory: str) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    for url, name in ((MODEL_URL, MODEL_NAME), (RUNTIME_URL, RUNTIME_NAME)):
        urllib.request.urlretrieve(url, root / name)
    verify_files(root)


def verify_files(directory: Path | str) -> None:
    root = Path(directory)
    model = root / MODEL_NAME
    runtime = root / RUNTIME_NAME
    if not model.is_file() or model.stat().st_size != MODEL_BYTES or _sha256(model) != MODEL_SHA256:
        raise ValueError("model_sha")
    if not runtime.is_file() or runtime.stat().st_size != RUNTIME_BYTES or _sha256(runtime) != RUNTIME_SHA256:
        raise ValueError("runtime_sha")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    if command == "quote":
        minutes = int(args[1]) if len(args) > 1 else 90
        print(json.dumps(brain_plan(minutes)))
        return 0
    if command == "fetch":
        fetch(args[1])
        return 0
    if command == "verify":
        verify_files(args[1])
        return 0
    print("usage: redteam_brain.py quote [minutes]|fetch DIR|verify DIR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
