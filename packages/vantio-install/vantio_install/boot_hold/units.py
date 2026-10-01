"""systemd units for the boot hold, early Phantom Engine start, and workload gate."""

from __future__ import annotations

from vantio_install.boot_hold.constants import NETWORK_NAME, SUBNET_V4
from vantio_install.boot_hold.policy import mechanisms_active


def _py(python: str, args: str) -> str:
    return f"{python} -m vantio_install.boot_hold {args}"


def boot_hold_service(python: str) -> str:
    return f"""[Unit]
Description=Hold enrolled workloads before Docker and before workload services
DefaultDependencies=no
After=local-fs.target
Before=docker.service containerd.service vantio-pe-loader.service
# SSH, systemd-networkd, resolved, and SSM are not ordered behind this unit.

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=30
Environment=VANTIO_BOOT_HOLD_LIVE=1
ExecStart={_py(python, "apply-boot")}

[Install]
WantedBy=sysinit.target
"""


def pe_loader_service(python: str) -> str:
    return f"""[Unit]
Description=Start Phantom Engine as early as the enrolled hold allows
DefaultDependencies=no
After=local-fs.target vantio-boot-hold.service docker.service
Wants=docker.service
Before=vantio-pe-enforce-ready.service

[Service]
Type=simple
Restart=no
Environment=VANTIO_BOOT_HOLD_LIVE=1
ExecStart={_py(python, "start-loader")}
ExecStop=/bin/kill -TERM $MAINPID

[Install]
WantedBy=multi-user.target
"""


def enforce_ready_service(python: str) -> str:
    return f"""[Unit]
Description=Release the enrolled hold only after Phantom Engine is enforce-ready
DefaultDependencies=no
After=vantio-pe-loader.service vantio-boot-hold.service
Requires=vantio-pe-loader.service

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=180
Environment=VANTIO_BOOT_HOLD_LIVE=1
ExecStart={_py(python, "release --require-enforce-ready --wait-seconds 120")}

[Install]
WantedBy=multi-user.target
"""


def enrolled_slice() -> str:
    return f"""[Unit]
Description=Enrolled workloads
DefaultDependencies=no
Before=slices.target

[Slice]
"""


def docker_ordering_dropin() -> str:
    return """[Unit]
After=vantio-boot-hold.service
"""


def enrolled_docker_service(policy: dict) -> str:
    hold, ordering = mechanisms_active(policy)
    after = ["docker.service", "vantio-enrolled-network.service"]
    requires = ["docker.service", "vantio-enrolled-network.service"]
    if hold:
        after.append("vantio-boot-hold.service")
        requires.append("vantio-boot-hold.service")
    if ordering:
        after.append("vantio-pe-enforce-ready.service")
        requires.append("vantio-pe-enforce-ready.service")
    return f"""[Unit]
Description=Start enrolled container %i after the boot gate
After={' '.join(after)}
Requires={' '.join(requires)}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker start %i
ExecStop=/usr/bin/docker stop %i

[Install]
WantedBy=multi-user.target
"""


def enrolled_network_service(python: str) -> str:
    return f"""[Unit]
Description=Create the enrolled Docker network {NETWORK_NAME} ({SUBNET_V4})
After=docker.service vantio-boot-hold.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
Environment=VANTIO_BOOT_HOLD_LIVE=1
ExecStart={_py(python, "ensure-network")}

[Install]
WantedBy=multi-user.target
"""


def compose_service(name: str, project_dir: str, policy: dict) -> str:
    hold, ordering = mechanisms_active(policy)
    after = ["docker.service", "vantio-enrolled-network.service"]
    requires = ["docker.service", "vantio-enrolled-network.service"]
    if hold:
        after.append("vantio-boot-hold.service")
        requires.append("vantio-boot-hold.service")
    if ordering:
        after.append("vantio-pe-enforce-ready.service")
        requires.append("vantio-pe-enforce-ready.service")
    safe_dir = project_dir
    return f"""[Unit]
Description=Start enrolled compose project {name} after the boot gate
After={' '.join(after)}
Requires={' '.join(requires)}

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={safe_dir}
ExecStart=/usr/bin/docker compose start
ExecStop=/usr/bin/docker compose stop

[Install]
WantedBy=multi-user.target
"""


def static_units(python: str, policy: dict) -> dict[str, str]:
    return {
        "etc/systemd/system/vantio-boot-hold.service": boot_hold_service(python),
        "etc/systemd/system/vantio-pe-loader.service": pe_loader_service(python),
        "etc/systemd/system/vantio-pe-enforce-ready.service": enforce_ready_service(python),
        "etc/systemd/system/vantio-enrolled.slice": enrolled_slice(),
        "etc/systemd/system/vantio-enrolled-docker@.service": enrolled_docker_service(policy),
        "etc/systemd/system/vantio-enrolled-network.service": enrolled_network_service(python),
        "etc/systemd/system/docker.service.d/vantio-boot-hold.conf": docker_ordering_dropin(),
        "etc/systemd/system/containerd.service.d/vantio-boot-hold.conf": docker_ordering_dropin(),
    }


def wants_links() -> dict[str, str]:
    """Symlink path -> relative target, as systemd enable would write them."""

    return {
        "etc/systemd/system/sysinit.target.wants/vantio-boot-hold.service": "../vantio-boot-hold.service",
        "etc/systemd/system/multi-user.target.wants/vantio-pe-loader.service": "../vantio-pe-loader.service",
        "etc/systemd/system/multi-user.target.wants/vantio-pe-enforce-ready.service": "../vantio-pe-enforce-ready.service",
        "etc/systemd/system/multi-user.target.wants/vantio-enrolled-network.service": "../vantio-enrolled-network.service",
    }
