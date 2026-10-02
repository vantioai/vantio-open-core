"""Pins for the enrolled-only boot hold."""

from __future__ import annotations

from vantio_install import constants as install_constants

REBOOT_ROW = "NOT_PROVED"
PROOF_STATE = install_constants.PROOF_STATE
PROOF_CEILING = install_constants.PROOF_CEILING

SLICE = "vantio-enrolled.slice"
CGROUP_ROOT = "/sys/fs/cgroup"
SLICE_PATH = f"{CGROUP_ROOT}/{SLICE}"
CHAIN = "VANTIO_BOOT_HOLD"
SUBNET_V4 = "10.250.250.0/24"
SUBNET_V6 = "fd76:616e:7469::/64"
NETWORK_NAME = "vantio-enrolled"
APPARMOR_PROFILE = "vantio-boot-hold"
ENFORCE_PROGRAM = "cgroup_skb_egress_enforce"
BPF_PINS = install_constants.BPF_PINS

STATE_DIR = "var/lib/vantio/boot-hold"
CONFIG_REL = "etc/vantio/boot-hold.json"
REGISTRY_REL = f"{STATE_DIR}/registry.json"
AUDIT_REL = f"{STATE_DIR}/audit.log"
HEALTH_REL = "run/vantio/boot-hold-health.json"
HOLD_STATE_REL = f"{STATE_DIR}/hold-state.json"
LOADER_ARGV_REL = "etc/vantio/pe-loader.argv.json"
EXPECTED_POLICY_REL = f"{STATE_DIR}/expected-policy-id"
ENFORCE_CONTAINER_REL = f"{STATE_DIR}/enforce-container-name"
COMMAND_REL = "usr/local/bin/vantio-boot-hold"
PROFILE_REL = "etc/apparmor.d/vantio-boot-hold"
DROPIN_NAME = "vantio-boot-hold.conf"

HELD_MESSAGE = (
    "Enrolled workloads are held. Phantom Engine is not enforce-ready, so the hold stays on. "
    "SSH and the console stay up. A root operator on the host can release with "
    "`vantio-boot-hold release --break-glass --i-am-root-operator`. "
    "An enrolled workload cannot release this hold."
)

RECOVERY_UNITS = frozenset(
    {
        "ssh.service",
        "sshd.service",
        "ssh.socket",
        "systemd-networkd.service",
        "systemd-networkd-wait-online.service",
        "systemd-resolved.service",
        "systemd-timesyncd.service",
        "dhcpcd.service",
        "amazon-ssm-agent.service",
        "snap.amazon-ssm-agent.amazon-ssm-agent.service",
        "docker.service",
        "containerd.service",
        "vantio-boot-hold.service",
        "vantio-pe-loader.service",
        "vantio-pe-enforce-ready.service",
        "vantio-enrolled-network.service",
    }
)
