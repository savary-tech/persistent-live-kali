#!/usr/bin/env python3
"""
Auto-detect ext4 partition labeled 'persistence' and create persistence.conf.

What it does:
- Finds the block device where: LABEL="persistence" and TYPE="ext4"
- Mounts it (unless already mounted)
- Writes / union into persistence.conf
- Syncs and unmounts (only if this script mounted it)

Usage:
  sudo python3 make_persistence_conf.py
  sudo python3 make_persistence_conf.py --device /dev/sdb3
  sudo python3 make_persistence_conf.py --label persistence
  sudo python3 make_persistence_conf.py --mount /mnt/my_usb
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

CONF_LINE = "/ union\n"


def run(cmd: list[str], check: bool = True) -> str:
    res = subprocess.run(cmd, text=True, capture_output=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout.strip()


def require_root():
    if os.geteuid() != 0:
        print("Run this with sudo/root.")
        print("Example: sudo python3 make_persistence_conf.py")
        sys.exit(1)


def find_device_by_label(label: str) -> str:
    # blkid -L <label> returns the device path if found
    dev = run(["blkid", "-L", label], check=False).strip()
    if not dev:
        raise RuntimeError(f'No device found with label "{label}".')

    info = run(["blkid", dev], check=False)
    if 'TYPE="ext4"' not in info:
        raise RuntimeError(f'Found {dev} with label "{label}", but it is not ext4. blkid says:\n{info}')
    return dev


def get_mount_target(device: str) -> str:
    # Returns mountpoint if mounted, else empty
    return run(["findmnt", "-rn", "-S", device, "-o", "TARGET"], check=False).strip()


def mount_device(device: str, preferred_mount: Path) -> tuple[Path, bool]:
    """
    Returns (mount_point, did_mount)
    did_mount=True only if this function performed the mount.
    """
    already = get_mount_target(device)
    if already:
        return Path(already), False

    preferred_mount.mkdir(parents=True, exist_ok=True)
    run(["mount", device, str(preferred_mount)])
    return preferred_mount, True


def write_conf(mount_point: Path):
    conf_path = mount_point / "persistence.conf"
    conf_path.write_text(CONF_LINE, encoding="utf-8")
    run(["sync"], check=False)
    print(f"Wrote {conf_path} with: {CONF_LINE.strip()}")


def unmount_if_needed(mount_point: Path, did_mount: bool):
    if did_mount:
        run(["umount", str(mount_point)])
        print(f"Unmounted {mount_point}")
    else:
        print(f"Left mounted (was already mounted): {mount_point}")


def main():
    require_root()

    ap = argparse.ArgumentParser(description="Create persistence.conf on ext4 partition labeled 'persistence'")
    ap.add_argument("--device", help="Device path like /dev/sdb3 (skip auto-detect)")
    ap.add_argument("--label", default="persistence", help='Partition label to search for (default: "persistence")')
    ap.add_argument("--mount", default="/mnt/kali_persistence", help="Mount point to use if not already mounted")
    args = ap.parse_args()

    device = args.device
    if device:
        info = run(["blkid", device], check=False)
        if not info:
            raise RuntimeError(f"Device not found or no blkid info: {device}")
        if 'TYPE="ext4"' not in info:
            raise RuntimeError(f"{device} is not ext4. blkid says:\n{info}")
        if f'LABEL="{args.label}"' not in info:
            print(f'Warning: {device} does not have LABEL="{args.label}". Continuing anyway...')
    else:
        device = find_device_by_label(args.label)

    print(f"Using device: {device}")

    mount_point, did_mount = mount_device(device, Path(args.mount))
    print(f"Mounted at: {mount_point}")

    write_conf(mount_point)
    unmount_if_needed(mount_point, did_mount)

    print('Done. Reboot and choose: "Live system (persistence)"')


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
