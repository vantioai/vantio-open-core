# Customer-path friction

UTC: 2026-10-17T00:15:00Z

This note does not start the soak. 2C through 2G and the 36-hour soak still wait for the `eac53556` post-reboot proof: errno 13 on the enrolled secret while the loader is up. That proof is not recorded. Host `i-0c6fc2669bb5ceff4` is on boot `6aa4f5cb-32ef-4e80-be39-51f0b8787ff1` and expires `2026-10-17T06:33:22Z`. Open-core #327 is green at `4095b747f9adefe60cecfee9fc65a89ff17c2e32` and is not merged. The lab workflows run from `main`.

When that proof is recorded, the install, upgrade, rollback, and uninstall on the host use the customer pages and the sealed bundle. A step that exists only so the lab can read a result stays out of that install and is named in the run record.

## What the customer path is

The customer pages are:

- `packages/vantio-install/README.md`
- `packages/vantio-install/docs/QUICKSTART.md`
- `packages/vantio-install/docs/INSTALL.md`
- `packages/vantio-install/docs/UNINSTALL.md`
- `packages/vantio-install/docs/PREFLIGHT.md`

The commands on that path are:

1. `sha256sum` on the sealed wheel, compared with `SHA256SUMS`.
2. `python3 -m venv /var/lib/vantio/installer-venv` and `pip install --no-index --disable-pip-version-check --no-deps` of that wheel.
3. `vantio-install plan --bundle <bundle> --config <config> --json`, which writes `PLAN.json` and `PREFLIGHT.json`.
4. `VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install apply --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`.
5. `VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install uninstall --transaction-id <id> --scope all --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`.
6. `vantio-install verify-removal` for that scope.

`QUICKSTART.md` forbids cloning this repository on that path. It also forbids pulling Phantom Engine from GHCR.

`scripts/gap/t1-stranger-host/preflight.sh` is the stranger-host operator preflight. It lives in the repository and calls `stranger_host.py preflight`. It is not the customer preflight. The customer preflight is the `PREFLIGHT.json` that `vantio-install plan` writes. `docs/planning/clean-host-lifecycle/scripts/preflight.sh` is an internal clean-host guard. It is not the customer preflight either.

The private lab bundle used for `eac53556` contains `seal.oci.tar`, `public-pin.oci.tar`, `contract.tar`, and `manifest.json`. It does not contain a README, `preflight.sh`, or the sealed `vantio-install` wheel.

## Friction

1. The lab batteries run `scripts/aws/lab-guests/enterprise-rows.sh` from a GitHub Actions checkout. That script loads the seal with `sudo docker load`, switches apt to offline mode, can add a swapfile, and can rewrite the Docker daemon config. `docs/gap/t1-stranger-host/STRANGER_HOST_STANDARD.md` already says a clean customer installer is not what that battery validated. A customer apply forbids raw `docker` and raw `sudo docker`. The install has to be the `vantio-install apply` command above. The shell script stays a lab step.

2. Customer apply is observe-only. `INSTALL.md` leaves enforcement `NOT_ENABLED`. The README says the live apply runs an allowlisted observe-only command list. The proof batteries need an enforcing loader. No command in `INSTALL.md` turns enforcement on. Starting the loader with the lab grant, revoke, and `VANTIO_PHANTOM_DENY` is an insider step until a customer command does that job. The run record has to say so.

3. Customer preflight check `PF-LSM` is `BLOCKED` when `/sys/kernel/security/lsm` has no `bpf` token. The remediation text is: reboot so that list contains `bpf`, then rerun preflight. `vantio-install` does not write `lsm=` into grub. `lsm_cmdline_with_bpf` returns an `lsm=` value only when consent is true, and that function does not edit the bootloader and does not reboot. The candidate loader log says the opposite in one sentence: "The installer writes that line only after explicit operator consent." Those two texts do not describe the same step. The lab `lsm-guard` battery is the program that writes the line and schedules `vantio-lab-lsm-reboot`. On a stock Noble image that line is required before enforcement can engage. Until the customer pages contain the write, the grub edit stays a named lab step.

4. The stranger-host `preflight.sh` also stops on `bpf_lsm_inactive` before any other check. Using it requires the repository checkout that `QUICKSTART.md` forbids. A customer-path run uses `vantio-install plan` for preflight. If the operator script is still copied onto the host to record the same facts, that copy is a lab evidence step.

5. `2c-upgrade-rollback` in the lab downloads `public-pin.oci.tar` with the private bundle token and loads it beside `seal.oci.tar`. The public pin stays `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`. A customer is not given that token or that second tar. Customer rollback is `vantio-install rollback` with the same plan hash and the same two live gates. The four-step pin, seal, pin, seal cycle is a lab measurement. The errno and uninstall readings around it stay a separate evidence step.

6. Customer uninstall is `vantio-install uninstall` plus `verify-removal`. The lab uninstall runs `vantio-loader --uninstall --confirm uninstall` with `VANTIO_ENTERPRISE_UNINSTALL_APPROVAL` set from `/var/lib/vantio/enterprise-uninstall.token`, then a census script. `UNINSTALL.md` names that token for an enrolled host. Calling the loader binary by hand, and writing `/var/lib/vantio-lab/vantio-uninstall.out`, are lab steps.

7. `2d-crash-recovery`, `2e-performance`, and `2f-tamper` do not install or remove the product. They open a file, time a revoke, or change a policy after the loader is up. Those probes stay lab evidence. They run only after the customer install is the thing on the host.

8. `2g-distro` on Ubuntu 24.04 can use the same customer install. The supported host in the README is Ubuntu 24.04 LTS on x86_64. Jammy, Amazon Linux 2023, and Debian 12 are a lab matrix. Launching those AMIs, choosing `ubuntu`, `admin`, or `ec2-user`, and grading them in `phase2_host.py` are lab steps. An `AccessDenied` on `RunInstances` stays a named residual. It is not a customer install failure.

9. The 36-hour soak in `w3-lab-auto-long-soak.yml` holds `vantio-lab-slot` and runs `soak-hourly.sh`, which the lab runner copies onto the host. A customer leaves the installed node up. The hourly probe, the Actions workflow, and the slot lease are lab evidence. They are not part of the install.

10. These collections stay lab-only and have to be named on each run: Instance Connect or IAP copy of the bundle, `W3_LAB_PRIVATE_BUNDLE_TOKEN`, the rows file `/var/lib/vantio-lab/enterprise-pe-rows.json`, `bpftool` listings, the enrolled-secret errno probe, `boot_id`, and the workflow artifact upload. None of those are `plan`, `apply`, `rollback`, `uninstall`, or `verify-removal`.

11. The candidate seal `eac53556ab35066a6849c35180aa83e49fe23748f108e61c6e97b18be47b3e07` is in the private lab bundle only. It is not the public installer pin. A customer-path run after the proof still has to be handed that sealed bundle. Cloning the private repository to fetch it is an insider step.

## What this does not change

The soak decision stays on the proof. This file does not merge #327, does not reboot the lab host, and does not mark a capability Shipped. `lab_pass` stays false. The public pin stays `e0b19d55`.
