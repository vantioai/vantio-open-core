# Host prep

You prepare the host before `vantio-install plan` can pass `PF-LSM`. Read `/sys/kernel/security/lsm`. When `bpf` is missing as its own comma-separated token, write an `lsm=` value that keeps the current tokens in order and appends `bpf`, install the executable drop-in below, regenerate grub, check the boot lines, and reboot. Then rerun plan.

`vantio-install` leaves the bootloader alone. It does not reboot the host. Apply stays observe-only, and enforcement stays `NOT_ENABLED`. This page does not turn enforcement on.

`vantio-install rollback` and `vantio-install uninstall` leave `/etc/default/grub.d/99-vantio-lsm.cfg` in place. You remove that file with the undo steps at the end of this page.

## What the sealed loader prints

When `bpf` is missing, the sealed loader prints these lines and exits:

```
Vantio Phantom Engine
not enforcing
bpf is not in the active LSM list. Add lsm=...,bpf and reboot. The installer writes that line only after explicit operator consent.
```

Follow this page for that case. The sentence "The installer writes that line only after explicit operator consent." does not describe `vantio-install`. You write the line, and you reboot. A later seal can replace the sentence in the loader. Until then, this page is the procedure that matches the installer.

## Read the live list

```bash
cat /sys/kernel/security/lsm
```

`bpf` counts only when it is its own comma-separated token. A longer token that contains those letters does not count. When `bpf` is already its own token, stop here.

On a stock Ubuntu 24.04 cloud image the list is `lockdown,capability,landlock,yama,apparmor,ima,evm`. The value you write for that list is `lockdown,capability,landlock,yama,apparmor,ima,evm,bpf`. For any other list, append `,bpf` and leave the earlier tokens in the order you read. Do not reorder them.

## Back up the bootloader files

```bash
sudo cp -a /etc/default/grub /etc/default/grub.vantio-backup
sudo cp -a /boot/grub/grub.cfg /boot/grub/grub.cfg.vantio-backup
if [ -d /etc/default/grub.d ]; then sudo cp -a /etc/default/grub.d /etc/default/grub.d.vantio-backup; fi
```

## Write the drop-in

Ubuntu cloud images source `40-force-partuuid.cfg` and `50-cloudimg-settings.cfg` from `/etc/default/grub.d` after `/etc/default/grub`. `40-force-partuuid.cfg` sets `GRUB_FORCE_PARTUUID`. `50-cloudimg-settings.cfg` assigns `GRUB_CMDLINE_LINUX_DEFAULT`. The tokens the image boots often live on `GRUB_CMDLINE_LINUX` as well. A line that exists only in `/etc/default/grub` can be overwritten. `/etc/default/grub.d/99-vantio-lsm.cfg` is sourced after those files. The script removes any existing `lsm=` token from `GRUB_CMDLINE_LINUX_DEFAULT` and from `GRUB_CMDLINE_LINUX`, then appends the same `lsm=` value to both.

The file has to be executable. `grub-mkconfig` skips a drop-in that is not executable.

The block below is the stock Ubuntu 24.04 value. If your live list differs, replace both `lsm=` values with your list plus `,bpf`, and keep `bpf` last.

```bash
sudo tee /etc/default/grub.d/99-vantio-lsm.cfg >/dev/null <<'EOF'
# Operator host prep. Sourced after the cloud image grub files.
_vantio_default=""
_vantio_linux=""
for _vantio_tok in $GRUB_CMDLINE_LINUX_DEFAULT; do
  case $_vantio_tok in
    lsm=*) ;;
    *) _vantio_default="$_vantio_default $_vantio_tok" ;;
  esac
done
for _vantio_tok in $GRUB_CMDLINE_LINUX; do
  case $_vantio_tok in
    lsm=*) ;;
    *) _vantio_linux="$_vantio_linux $_vantio_tok" ;;
  esac
done
GRUB_CMDLINE_LINUX_DEFAULT="${_vantio_default# } lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
GRUB_CMDLINE_LINUX="${_vantio_linux# } lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
unset _vantio_tok _vantio_default _vantio_linux
EOF
sudo chmod 0755 /etc/default/grub.d/99-vantio-lsm.cfg
```

## Regenerate grub and check the boot lines

```bash
sudo update-grub
```

Open `/boot/grub/grub.cfg`. On an image that sets `GRUB_FORCE_PARTUUID`, the line that boots contains `panic=-1`. Every such line's last `lsm=` word is `lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf`, or your own value if the live list was different. The kernel keeps the last `lsm=` word and ignores earlier copies. `panic=-1` can remain the last word of that line. An `lsm=` word that appears only on the fallback line leaves the booted line unchanged.

When a boot line's last `lsm=` word is different, restore the backups in the undo section and stop. Leave the host on the current boot.

## Reboot

You reboot the host. After it comes back, read both files:

```bash
cat /sys/kernel/security/lsm
cat /proc/cmdline
```

`bpf` is its own token in the LSM list, and the cmdline contains the `lsm=` word you wrote. Rerun `vantio-install plan`. `PF-LSM` stays `BLOCKED` until that token is present. The check text is: reboot so `/sys/kernel/security/lsm` lists `bpf`, then rerun preflight. A host without that token is not healthy and is not protected.

## Undo the drop-in

```bash
sudo rm -f /etc/default/grub.d/99-vantio-lsm.cfg
sudo cp -a /etc/default/grub.vantio-backup /etc/default/grub
sudo cp -a /boot/grub/grub.cfg.vantio-backup /boot/grub/grub.cfg
if [ -d /etc/default/grub.d.vantio-backup ]; then sudo rm -rf /etc/default/grub.d && sudo cp -a /etc/default/grub.d.vantio-backup /etc/default/grub.d; fi
sudo update-grub
```

You reboot after `update-grub`. Confirm the boot lines in `/boot/grub/grub.cfg` before that reboot. Product rollback does not run these commands.
