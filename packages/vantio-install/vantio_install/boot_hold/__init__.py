"""Early boot hold for enrolled workloads.

The hold is a host mechanism. It does not read Phantom Engine BPF pins to
install itself, and it does not mark the reboot exposure row proved.
"""

from vantio_install.boot_hold.constants import REBOOT_ROW

__all__ = ["REBOOT_ROW"]
