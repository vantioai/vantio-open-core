# Preflight

`vantio-install plan` writes `PREFLIGHT.json` under the transaction directory and copies it to the evidence directory. A customer plan reads the live host. Customer commands do not pass `--fixture-host`.

Docker availability and Docker privilege are different checks.

`PF-DOCKER` records whether the `docker` binary is on `PATH`. A binary on `PATH` does not grant permission to use the socket.

`PF-DOCKER-PERM` records how this principal is allowed to talk to Docker. The live probe sets `privilege_mode` to one of three strings:

- `docker_group` when `/var/run/docker.sock` exists and this principal can write it. `principal_can_talk_to_docker` is true.
- `sudo` when this principal cannot write that socket and `sudo` is on `PATH`. `sudo_available` is true.
- `UNKNOWN` when neither fact is true.

Root is effective uid 0. The probe does not store the string `root` in `privilege_mode`. A live `apply`, `rollback`, or `uninstall` accepts the command only when the effective uid is 0. `privilege_mode` `sudo` means `sudo` is on `PATH`. `privilege_mode` `docker_group` means this principal can write `/var/run/docker.sock`. Neither fact is a live grant, and the installer does not exec sudo.

`PF-DOCKER-PERM` is `PASS` when the principal can write the socket and `privilege_mode` is `docker_group` or `sudo`, or when `privilege_mode` is `sudo` and `sudo` is on `PATH`. The remediation stored on that check is: add the operator to the docker group, or rerun the installer with sudo. Group membership is not assumed. Rerun means `sudo` in front of `vantio-install`, so the installer process is root. It does not mean a Docker command typed by hand.

`PF-DOCKER-PERM` is `BLOCKED` when `privilege_mode` is `UNKNOWN` and the principal cannot write the socket. The plan overall is then `BLOCKED` when no unsupported check fired, the process exit is 2, and `state` stays off `PLANNED`. `PREFLIGHT.json` shows check id `PF-DOCKER-PERM`, the observed `privilege_mode`, and that remediation.

A live command returns `FAILED_SAFE` with the message `Live mutations need effective root. sudo on PATH is not privilege.` when the effective uid is not 0. A passing `sudo` or `docker_group` fact does not change that.

The installer is the only program on this path that runs Docker. It uses an argv list and `shell` is false. A shell string is refused. The executables it may run are `mkdir`, `npm`, `python3`, `docker`, `tc`, and `apparmor_parser`. `sudo`, `su`, and a shell are refused as the executable. An argument that contains a shell metacharacter is refused. An argv list that differs from the catalog entry for that step is refused.

Raw `docker`, raw `sudo docker`, and a direct call on `docker.sock` are forbidden for customer operators. So is changing the socket mode by hand. When the effective uid is not 0, rerun `vantio-install` under `sudo` so the process is root. A principal that can already write the socket is still not a live grant until that process is root. The allowlist does not insert `sudo` in front of `docker`. A host check can still fail when `docker` runs as a user who cannot open the socket.

`PF-OCI-LOAD` reads the sealed Phantom Engine OCI tar. It passes when the archive is not an OCI layout, when every layer's media type already matches its bytes, or when a mismatch can be corrected at apply. The correction writes a temporary load archive. The sealed file stays the file you hashed. Docker keeps the storage driver Ubuntu installed. The check blocks when the file is an OCI layout the installer cannot correct, for example a missing layer blob. Restore the sealed archive in that case.

`proof_state` stays `NOT_PROVED`. The proof ceiling stays `INTERNAL_CLEAN_HOST_PROOF`.
