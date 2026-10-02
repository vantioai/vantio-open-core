# Observe loader lifecycle

The sealed Phantom Engine loader is a long-running process. Apply starts it in a container, the process pins its maps, attaches the programs for the interface you named, and stays up. Ctrl-C, `docker stop`, rollback, and uninstall are what end it. A container that prints its banner and then exits is not a finished install.

`docker run -d` exiting 0 only means the daemon accepted the container. The host check does not treat that exit as success. It reads the container again for up to 20 seconds and returns as soon as every fact below is true. The 20 second bound stays where it is. The exported log for container `e63160e38f8d` already showed the active banner about a second after the container started, and the installer on that host had sampled once and stopped.

A successful observe install has all of these at the same time:

- The container status is `running`, the host pid is greater than 0, and the AppArmor profile is `vantio-pe-observe`.
- That pid's command is `vantio-loader` for the interface in the plan, without `--enforce`.
- The five known bpffs pins exist, and each one's mtime is at or after this container's start. Pins left by an earlier install do not count.
- The clsact qdisc is on that interface, and a bpf filter is attached on egress.
- The loader log has loaded the observe path maps and the enforce path maps, says the policy is observe-only audit, names the same interface, and has reached the line that tells you to press Ctrl-C.
- Boot hold status is `HELD`. A hold that has released itself as enforce-ready is not an observe pass. Observe-only apply does not run the enforce deny check.
- The cgroup sock-owner attachment is recorded when the log has it. The loader keeps running if that best-effort attach warns, so the warning alone does not fail the install. The required network path is the bpf filter on the named interface.

A stopped, dead, or removed container fails immediately, even when the pins are still there. Rollback then removes the container and the pins this transaction recorded. That rollback is for an install that did not meet the contract. It is not a signal to ignore a stopped container.

The check writes `HOST-CHECK.json` next to the transaction when it fails. The file names the missing facts. The next failure does not have to be reconstructed from a one-line error.
