#!/usr/bin/env python3
"""
Create/verify Kali persistence.conf on the ext4 partition labeled 'persistence'.

Run on Linux (Kali, Ubuntu, etc). Needs sudo/root because it mounts disks.
It will:
- find the block device with LABEL="persistence" (ext4)
- mount it to /mnt/kali_persistence
- create/overwrite persistence.conf with '/ union'
- sync + unmount

Usage:
  sudo python3 make_persistence_conf.py
"""

import os
import subprocess
import sys
from pathlib import Path

MOUNT_POINT = Path("/mnt/kali_persistence")
CONF_LINE = "/ union\n"


def run(cmd: list[str], check: bool = True) -> str:
    """Run command and return stdout (text)."""
    res = subprocess.run(cmd, check=check, text=True, capture_output=True)
    return res.stdout.strip()


def is_root() -> bool:
    return os.geteuid() == 0


def find_persistence_device() -> str:
    """
    Find device path via blkid by LABEL.
    Returns something like /dev/sdb3
    """
    try:
        # Example output line:
        # /dev/sdb3: LABEL="persistence" UUID="..." TYPE="ext4" PARTUUID="..."
        out = run(["blkid"])
    except subprocess.CalledProcessError as e:
        print("Error running blkid. Are you on Linux with util-linux installed?")
        print(e.stderr)
        sys.exit(1)

    candidates = []
    for line in out.splitlines():
        if 'LABEL="persistence"' in line and 'TYPE="ext4"' in line:
            dev = line.split(":", 1)[0].strip()
            candidates.append(dev)

    if not candidates:
        raise RuntimeError('No ext4 partition found with LABEL="persistence".')

    if len(candidates) > 1:
        # If you have multiple, pick the first but warn.
        print(f"Warning: multiple persistence-labeled partitions found: {candidates}")
    return candidates[0]


def is_mounted(device: str) -> bool:
    mounts = run(["findmnt", "-rn", "-S", device, "-o", "TARGET"], check=False)
    return bool(mounts)


def mount_device(device: str) -> None:
    MOUNT_POINT.mkdir(parents=True, exist_ok=True)

    # If device already mounted somewhere else, don't remount
    if is_mounted(device):
        target = run(["findmnt", "-rn", "-S", device, "-o", "TARGET"])
        print(f"{device} is already mounted at {target}")
        return

    run(["mount", device, str(MOUNT_POINT)])
    print(f"Mounted {device} -> {MOUNT_POINT}")


def write_conf() -> None:
    conf_path = MOUNT_POINT / "persistence.conf"
    conf_path.write_text(CONF_LINE, encoding="utf-8")
    print(f"Wrote {conf_path} with content: {CONF_LINE.strip()!r}")
    run(["sync"])


def unmount_device(device: str) -> None:
    # Only unmount if mounted at our mount point
    target = run(["findmnt", "-rn", "-S", device, "-o", "TARGET"], check=False)
    if target == str(MOUNT_POINT):
        run(["umount", str(MOUNT_POINT)])
        print(f"Unmounted {device} from {MOUNT_POINT}")
    elif target:
        print(f"Skipping unmount: {device} is mounted at {target} (not {MOUNT_POINT})")
    else:
        print(f"{device} is not mounted; nothing to unmount.")


def main():
    if not is_root():
        print("Run this with sudo/root:")
        print("  sudo python3 make_persistence_conf.py")
        sys.exit(1)

    try:
        device = find_persistence_device()
        print(f"Found persistence partition: {device}")

        mount_device(device)

        # If it was already mounted elsewhere, we can’t guarantee /mnt is correct.
        # In that case, write to the actual mount target.
        target = run(["findmnt", "-rn", "-S", device, "-o", "TARGET"], check=False)
        if target and target != str(MOUNT_POINT):
            global MOUNT_POINT
            MOUNT_POINT = Path(target)

        write_conf()
        unmount_device(device)

        print("Done. Reboot and choose: Live system (persistence)")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
