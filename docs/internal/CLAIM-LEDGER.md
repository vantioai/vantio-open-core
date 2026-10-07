# Internal claim ledger

Audience: INTERNAL_RESTRICTED. This file is not a public export. Packaging excludes `docs/internal/`.

## B1

B1 is closed at `INTERNAL_CLEAN_HOST_PROOF`. The closed row is one host, a graceful reboot, and seal `e0b19d55`.

Phantom Engine was enforcing before the boot hold released; the hold is not the only protection during startup.

The closed row does not use the sentence "no network activity before readiness."

These rows stay open:

- crash-reboot
- stranger-host
- post-#19-seal reruns

`CUSTOMER_SELF_INSTALL_PROTECTED_INTERNAL_PASS` stays the protected-path class. Closing the graceful-reboot row does not replace that class.

## Memory and DEGRADED

The bounded-memory class is hosts under 3 GiB. `PF-MEM` records `LIMITATION` and `RESOURCE_SUFFICIENT_FOR_BOUNDED_TEST` when total memory is under 3 GiB. When that limitation is present and the other health checks pass, health is `PASS_WITH_LIMITATIONS`, and apply maps `PASS_WITH_LIMITATIONS` to `DEGRADED`.

`DEGRADED` here is that bounded-memory result. It is not a failed install by itself.

A `t3.small` at 1.861 GiB is `DEGRADED` by design. The memory check is not weakened to make that host `HEALTHY`.
