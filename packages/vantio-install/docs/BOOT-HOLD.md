# Boot hold

Enrolled workloads stay held from early boot until Phantom Engine is enforce-ready. The hold is on by default. It covers enrolled workloads only: their network egress and the protected paths you listed at enrollment. SSH, cloud agents, DHCP, DNS, and every unenrolled process keep working. The host default route stays up.

The hold is a host mechanism. It is installed by `vantio-boot-hold.service` before Docker and containerd start. It does not read Phantom Engine BPF pins to install itself, and it does not need the Phantom Engine container to be running. Those pins are empty after a reboot until the loader attaches.

`vantio-install apply` installs and enables this hold. You do not run a second install command to get it. A trusted opt-out file is left alone, so apply does not turn the hold back on.

`vantio-boot-hold status` prints one JSON object. The same object is copied into the installer `HEALTH.json` as `boot_hold`. While the hold is in the packet filter and Phantom Engine is not enforce-ready, `state` is `HELD` and `health` is `DEGRADED`. The message tells you SSH is up and how a root operator releases the hold. `reboot_row` stays `NOT_PROVED`. This command does not mark a reboot exposure run as passed.

## What runs, and in what order

1. `vantio-boot-hold.service` runs from `sysinit.target`, before `docker.service` and `containerd.service`. It creates `vantio-enrolled.slice`, loads the AppArmor profile `vantio-boot-hold` in deny mode for the protected paths you enrolled, and inserts scoped iptables and ip6tables rules.
2. Docker starts. A drop-in orders Docker after the hold. Docker does not `Requires=` the hold, so a hold failure does not take Docker down. Enrolled containers stay stopped because their restart policy is `no`.
3. `vantio-pe-loader.service` starts Phantom Engine after the hold and after Docker. The loader command is a root-owned JSON list in `/etc/vantio/pe-loader.argv.json`. If that file is missing, the loader unit fails and enrolled workloads stay held.
4. `vantio-pe-enforce-ready.service` releases the hold only after a live check: the loader is up with `--enforce`, the pinned map names are current for this container start, the running command matches the policy id recorded by `prepare-enforce`, the mode is scoped or node-wide, `cgroup_skb_egress_enforce` is attached to `vantio-enrolled.slice`, loader health is OK, and a deny self-check sees a new `CG/SKB BLOCKED` line for a connect from inside the slice while the same connect from `system.slice` succeeds. The probe target is a local listener on `198.51.100.2` port `18080` that the check creates and removes. That address is outside the private ranges the sealed loader allows. The self-check opens one scoped exception in the hold chain for that destination, then removes it. A timeout with no new cgroup block line does not pass. A loader that is running but not attached does not pass. Audit mode does not pass. If the check fails, the unit fails, the hold stays, and enrolled units that require it stay stopped.
5. Enrolled workloads start from their own systemd units after enforce-ready.

Ordering and the hold are both on unless a root admin changes them. You can exercise one at a time with `configure`. Turning both off is an opt-out.

## Packet rules

The boot units set `VANTIO_BOOT_HOLD_LIVE=1` so the packet rules, the release, and the loader start run on the host. An admin shell that changes the hold exports the same variable. If `iptables` or `ip6tables` cannot insert the enrolled rules, the hold unit fails and enrolled units that require it stay stopped.

The filter chain is `VANTIO_BOOT_HOLD`. It drops two classes of traffic:

- OUTPUT packets whose socket is in `vantio-enrolled.slice` or a child of that slice (IPv4 and IPv6).
- FORWARD packets from `10.250.250.0/24` (IPv4) or `fd76:616e:7469::/64` (IPv6).

SSH, DHCP, and DNS are not in that slice and do not use that subnet, so their packets stay on the normal path. The rules do not change the default route.

## Protected files

Each enrolled systemd unit gets `Slice=vantio-enrolled.slice`. While the hold is up, the unit also gets `InaccessiblePaths=` for each protected path and `AppArmorProfile=vantio-boot-hold` when AppArmor loaded. Release removes the `InaccessiblePaths=` lines, reloads systemd, and replaces the AppArmor profile with an allow profile of the same name so the workload can start. Phantom Engine policy is the control after the enforce-ready probe.

A protected path is an absolute directory at least three levels deep, outside SSH keys and system directories such as `/etc`, `/usr`, and `/home` itself. `/var/lib/app/secrets` is a usable example. `/`, `/etc/ssh`, and `/root/.ssh` are refused.

## Plain Docker

Create the network and the container while the machine is up, with restart policy `no`. The systemd unit starts the container later.

```bash
docker network create --subnet 10.250.250.0/24 vantio-enrolled
docker run -d --name agent \
  --restart=no \
  --cgroup-parent=/vantio-enrolled.slice \
  --security-opt apparmor=vantio-boot-hold \
  --network vantio-enrolled \
  your-image
vantio-boot-hold enroll-docker \
  --name agent \
  --restart-policy no \
  --cgroup-parent /vantio-enrolled.slice \
  --protected-path /var/lib/app/secrets
```

`vantio-enrolled-docker@agent.service` runs `docker start agent` after `vantio-pe-enforce-ready.service`. A restart policy of `always`, `unless-stopped`, or `on-failure` is refused, because Docker would start that container in parallel with Phantom Engine. `enroll-docker --set-restart-no` runs `docker update --restart=no` and then enrolls.

`vantio-enrolled-network.service` creates the network after Docker is up. It does not start enrolled containers.

## Compose

The compose file uses restart `no`, the enrolled cgroup parent, the AppArmor profile, and the enrolled subnet. `vantio-boot-hold enroll-compose` refuses the file until those are present, and it installs a systemd unit whose `ExecStart` is `docker compose start`.

```yaml
services:
  agent:
    image: your-image
    restart: "no"
    cgroup_parent: /vantio-enrolled.slice
    security_opt:
      - apparmor:vantio-boot-hold
    networks:
      - enrolled
networks:
  enrolled:
    name: vantio-enrolled
    ipam:
      config:
        - subnet: 10.250.250.0/24
```

```bash
vantio-boot-hold enroll-compose \
  --project-dir /var/lib/app/compose \
  --compose-file /var/lib/app/compose/compose.yaml
```

Create the containers with `docker compose create` in that directory before reboot. The systemd unit starts them after enforce-ready.

## systemd services

```bash
vantio-boot-hold enroll-systemd \
  --unit my-agent.service \
  --protected-path /var/lib/app/secrets
```

The drop-in `/etc/systemd/system/my-agent.service.d/vantio-boot-hold.conf` sets `Slice=vantio-enrolled.slice`, `After=` and `Requires=` `vantio-boot-hold.service`, and, when ordering is on, `After=` and `Requires=` `vantio-pe-enforce-ready.service`.

The Phantom Engine loader enrolls that slice. A root-owned `/etc/vantio/pe-loader.argv.json` can be:

```json
["/usr/bin/docker", "start", "-a", "vantio-pe"]
```

Create the Phantom Engine container with `vantio-boot-hold prepare-enforce --iface IFACE --observe-name OBSERVE`. That command creates `vantio-enrolled.slice` first, stops the observe container you name, and starts `vantio-pe` with host networking, `--cgroupns=host`, the host cgroup tree mounted, `--restart=no`, `--enforce`, `--cgroup-skb-enforce`, and `--startup-enroll-cgroup /sys/fs/cgroup/vantio.slice/vantio-enrolled.slice`. The container stays out of `vantio-enrolled.slice`. The open-core unit starts it again on the next boot. The image tag stays the pinned seal tag. This package does not invent a seal.

SSH, `systemd-networkd`, resolved, SSM, Docker, and the hold units themselves cannot be enrolled.

## When the loader does not start

Enrolled workloads stay held. `vantio-boot-hold status` shows `HELD` and `DEGRADED`, with the operator message. SSH and the console still come up, because those units are not ordered behind the hold and they are not in the enrolled slice.

Release is a root action on the host and it is written to `/var/lib/vantio/boot-hold/audit.log`.

- After the probe passes, `vantio-pe-enforce-ready.service` runs `vantio-boot-hold release --require-enforce-ready`.
- If the probe fails, that command refuses and the hold stays.
- A root operator at the console can run `vantio-boot-hold release --break-glass --i-am-root-operator`. That one action removes the packet hold, clears the file hold, and drops `Requires=` on enforce-ready and on the boot-hold unit for enrolled systemd, Docker, and Compose units. The audit line lists each item released, including `packet-hold-ipv4`, `packet-hold-ipv6`, `file-hold`, and `start-gate:<unit>`. Health stays `DEGRADED` because Phantom Engine was not enforce-ready. The next boot installs the hold again unless you opted out.

The command refuses a caller whose cgroup is under `vantio-enrolled.slice`, a caller outside the host init namespace, and any caller who is not root. An enrolled workload cannot release the hold. There is no silent release.

## Default and opt-out

A missing `/etc/vantio/boot-hold.json` means the hold and ordering are on. Opt out with:

```bash
vantio-boot-hold opt-out --reason "maintenance window approved by the host admin"
```

The file must be owned by root and must not be group or world writable. A looser file is ignored and the hold stays on. `status` shows `OPTED_OUT`. Turn it back on with `vantio-boot-hold opt-in`.

Hold alone, or ordering alone:

```bash
vantio-boot-hold configure --hold on --ordering off
vantio-boot-hold configure --hold off --ordering on
```

Both of those are logged. `configure` refuses to turn both off. Use `opt-out` for that.

Live packet changes on the host run only when you are root, `--root /`, and `VANTIO_BOOT_HOLD_LIVE=1`. Any other invocation records the commands and writes under `--root` so a fixture can exercise them.

## Workloads that are not enrolled

A workload that is missing from `/var/lib/vantio/boot-hold/registry.json` is unprotected. `status --lookup NAME` prints `protection: UNPROTECTED` for that name. Record a known unenrolled control explicitly:

```bash
vantio-boot-hold observe-unenrolled --id unenrolled-probe --kind systemd
```

The hold does not apply to it. Status keeps showing it as unprotected.

## Install the units

```bash
vantio-boot-hold install
```

That writes the units, the Docker and containerd `After=vantio-boot-hold.service` drop-ins, and the enable symlinks. The next boot runs the hold before Docker. `status` before `apply-boot` says `CONFIGURED`, which means the packet filter is not installed yet.
