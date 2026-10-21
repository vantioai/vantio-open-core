"""Both live gates, on every mutating command."""

from __future__ import annotations

import os

from vantio_install import constants
from vantio_install.errors import InstallError
from vantio_install.util import now_et

_MESSAGE = "Live mutations need VANTIO_INSTALL_ALLOW_LIVE=1 and --i-accept-live-mutations together."


def require_live_gates(ctx: dict) -> None:
    env_open = os.environ.get("VANTIO_INSTALL_ALLOW_LIVE") == "1"
    flag = bool(ctx.get("accept_live_mutations"))
    if not env_open or not flag:
        raise InstallError(_MESSAGE, exit_code=4, state="FAILED_SAFE")
    if ctx.get("fixture_host"):
        return
    euid = ctx.get("live_euid")
    if euid is None:
        euid = os.geteuid()
    if int(euid) != 0:
        raise InstallError(
            "Live mutations need effective root. sudo on PATH is not privilege.",
            exit_code=4,
            state="FAILED_SAFE",
        )


def command_payload(command: str, state: str, message: str, **extra: object) -> dict:
    body = {
        "command": command,
        "transaction_id": extra.pop("transaction_id", None),
        "state": state,
        "evidence_dir": extra.pop("evidence_dir", None),
        "proof_state": constants.PROOF_STATE,
        "proof_ceiling": constants.PROOF_CEILING,
        "as_of_et": extra.pop("as_of_et", now_et()),
        "message": message,
        "installer_version": constants.INSTALLER_VERSION,
    }
    body.update(extra)
    return body
