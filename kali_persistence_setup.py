#!/usr/bin/env python3
"""
Kali Live USB persistence setup (Linux only).

Assumes:
- You already flashed the Kali Live ISO to a USB drive (dd/Rufus DD mode).
- The drive currently has 2 partitions from the ISO (common layout).
This script will:
1) Detect the USB drive (or use --device)
2) Create partition #3 filling remaining space
3) mkfs.ext4 -L persistence on partition #3
4) Create persistence.conf containing "/ union"

Usage:
  sudo python3 kali_persistence_setup.py
  sudo python3 kali_persistence_setup.py --device /dev/sdb
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MOUNT_POINT = Path("/mnt/kali_persistence")
CONF_CONTENT = "/ union\n"

def run(cmd, check=True):
    r = subprocess.run(cmd, text=True, capture_output=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()

def require_root():
    if os.geteuid() != 0:
        print("Run as root (sudo). Example:")
        print("  sudo python3 kali_persistence_setup.py")
        sys.exit(1)

def lsblk_json():
    # -b for bytes, -J for json, include filesystem info
    out = run(["lsblk", "-bJ", "-o", "NAME,PATH,TYPE,SIZE,RM,RO,FSTYPE,LABEL,PARTTYPE,PARTLABEL,MOUNTPOINTS"])
    return json.loads(out)

def human(n):
    # simple
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"

def find_kali_usb_candidate(tree):
    """
    Try to auto-detect the Kali Live USB.
    Heuristics:
      - disk with RM=1 (removable) (not always reliable but helps)
      - has a ~4-7GB partition that is iso9660 or vfat (hybrid ISO)
      - has a tiny partition (1-8MB) often partition #2
      - total disk size >= 8GB
    If multiple candidates, we refuse unless user passes --device.
    """
    disks = [d for d in tree.get("blockdevices", []) if d.get("type") == "disk"]
    candidates = []

    for d in disks:
        path = d.get("path")
        size = int(d.get("size") or 0)
        rm = int(d.get("rm") or 0)

        if size < 8 * 1024**3:
            continue

        children = d.get("children") or []
        if len(children) < 2:
            continue

        # Look for ISO-ish partition
        isoish = False
        tiny = False
        for p in children:
            psize = int(p.get("size") or 0)
            fstype = (p.get("fstype") or "").lower()
            label = (p.get("label") or "").lower()

            if (4 * 1024**3) <= psize <= (8 * 1024**3) and (fstype in ["iso9660", "vfat", "fat", "fat32"] or "kali" in label):
                isoish = True
            if (1 * 1024**2) <= psize <= (8 * 1024**2):
                tiny = True

        if isoish and tiny:
            # rm helps but don't require it
            score = 2 + (1 if rm == 1 else 0)
            candidates.append((score, path, d))

    candidates.sort(reverse=True, key=lambda x: x[0])

    if not candidates:
        return None, "No obvious Kali-flashed USB found."

    # If multiple, this is too risky to guess.
    top_score = candidates[0][0]
    top = [c for c in candidates if c[0] == top_score]
    if len(top) != 1:
        msg = "Multiple possible USB disks found. Use --device to specify one:\n"
        for _, path, d in candidates[:10]:
            msg += f"  {path}  size={human(int(d.get('size') or 0))}  rm={d.get('rm')}\n"
        return None, msg

    return candidates[0][1], None

def get_part_paths(tree, disk_path):
    disks = tree.get("blockdevices", [])
    for d in disks:
        if d.get("path") == disk_path and d.get("type") == "disk":
            children = d.get("children") or []
            parts = []
            for p in children:
                if p.get("type") == "part":
                    parts.append(p.get("path"))
            # Sort by partition number if possible
            def partnum(p):
                m = re.search(r"(\d+)$", p)
                return int(m.group(1)) if m else 999
            parts.sort(key=partnum)
            return parts
    return []

def wait_for_kernel():
    # Give udev a moment after partitioning
    time.sleep(1.2)
    run(["udevadm", "settle"], check=False)

def disk_is_mounted(disk_path):
    # If any partition mounted, return True
    mp = run(["lsblk", "-nr", "-o", "MOUNTPOINTS", disk_path], check=False)
    return bool(mp.strip())

def unmount_all_partitions(disk_path):
    # Unmount any mounted partitions on the disk (best effort)
    parts = run(["lsblk", "-nr", "-o", "PATH,MOUNTPOINTS", disk_path], check=False).splitlines()
    # lines include disk too; focus on partitions with mountpoints
    for line in parts:
        cols = line.split(None, 1)
        if not cols:
            continue
        path = cols[0]
        if path == disk_path:
            continue
        if len(cols) == 2 and cols[1].strip():
            # may be multiple mountpoints separated by \n? lsblk prints spaces.
            mps = cols[1].split()
            for mp in mps:
                run(["umount", "-f", mp], check=False)

def get_free_region_mib(disk_path):
    """
    Use parted to find free space region after the last partition.
    Returns (start_mib, end_mib) or None.
    """
    out = run(["parted", "-sm", disk_path, "unit", "MiB", "print", "free"])
    # parted -sm output example lines:
    # BYT;
    # /dev/sdb:59668MiB:scsi:512:512:msdos:...
    # 1:0.00MiB:4700MiB:4700MiB:primary:iso9660:...
    # 2:4700MiB:4704MiB:4.00MiB:primary::...
    # :4704MiB:59668MiB:54964MiB:free;
    free_lines = [ln for ln in out.splitlines() if ln.endswith(":free;") or ":free:" in ln]
    # Prefer the last free region (end of disk)
    if not free_lines:
        return None

    # Parse all free regions and choose the one with the largest end (closest to end)
    regions = []
    for ln in free_lines:
        parts = ln.split(":")
        # format: <num or empty>:<start>:<end>:<size>:free;
        if len(parts) < 5:
            continue
        start = parts[1]
        end = parts[2]
        if start.endswith("MiB") and end.endswith("MiB"):
            s = float(start.replace("MiB",""))
            e = float(end.replace("MiB",""))
            if e - s >= 32:  # must be at least 32MiB to be useful
                regions.append((s, e))

    if not regions:
        return None

    regions.sort(key=lambda x: x[1], reverse=True)
    return regions[0]

def create_partition3(disk_path):
    """
    Create a new primary partition in the last free region.
    Uses parted. Works on MBR and GPT.
    """
    region = get_free_region_mib(disk_path)
    if not region:
        raise RuntimeError("No usable unallocated space found on the disk. You may need to shrink a partition first.")

    start, end = region
    # Align start a bit (MiB alignment)
    start_aligned = round(start + 1.0, 2)  # +1MiB for safety
    if end - start_aligned < 32:
        raise RuntimeError("Not enough free space after alignment to create persistence partition.")

    # mkpart needs: name (optional on gpt), type, start, end
    # We'll just do mkpart primary ext4 <start> <end>
    run(["parted", "-s", disk_path, "mkpart", "primary", "ext4", f"{start_aligned}MiB", f"{end}MiB"])
    wait_for_kernel()

def partition_path(disk_path, n):
    """
    /dev/sdb + 3 -> /dev/sdb3
    /dev/nvme0n1 + 3 -> /dev/nvme0n1p3
    """
    base = Path(disk_path).name
    if base.startswith("nvme") or base.startswith("mmcblk"):
        return f"{disk_path}p{n}"
    return f"{disk_path}{n}"

def ensure_ext4_persistence(part_path):
    # If already labeled persistence ext4, keep it.
    blk = run(["blkid", part_path], check=False)
    if 'TYPE="ext4"' in blk and 'LABEL="persistence"' in blk:
        return

    # Format ext4 and label persistence
    run(["mkfs.ext4", "-F", "-L", "persistence", part_path])
    wait_for_kernel()

def mount_and_write_conf(part_path):
    MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    # mount
    run(["mount", part_path, str(MOUNT_POINT)])
    try:
        conf = MOUNT_POINT / "persistence.conf"
        conf.write_text(CONF_CONTENT, encoding="utf-8")
        run(["sync"], check=False)
    finally:
        run(["umount", str(MOUNT_POINT)])

def main():
    require_root()

    ap = argparse.ArgumentParser(description="Create Kali persistence partition + persistence.conf on a flashed USB")
    ap.add_argument("--device", help="Disk device like /dev/sdb (recommended if you have multiple USBs)")
    args = ap.parse_args()

    tree = lsblk_json()

    disk = args.device
    err = None
    if not disk:
        disk, err = find_kali_usb_candidate(tree)
        if err:
            print(err)
            print("\nTip: run `lsblk` and then rerun with --device /dev/sdX")
            sys.exit(1)

    if not os.path.exists(disk):
        print(f"Device not found: {disk}")
        sys.exit(1)

    # Safety: refuse if disk is your system disk (common patterns)
    # Not perfect, but reduces accidental nukes.
    sys_disk_mps = run(["findmnt", "-nro", "SOURCE", "/"], check=False)
    if sys_disk_mps and sys_disk_mps.startswith(disk):
        print(f"Refusing: {disk} appears to contain your root filesystem ({sys_disk_mps}).")
        sys.exit(1)

    # Another safety: if disk has any mounted partitions, unmount them first
    if disk_is_mounted(disk):
        print(f"{disk} has mounted partitions. Unmounting them (best effort)...")
        unmount_all_partitions(disk)

    tree = lsblk_json()
    parts = get_part_paths(tree, disk)

    # If persistence already exists by label, just write conf
    blkid_all = run(["blkid"], check=False)
    if 'LABEL="persistence"' in blkid_all:
        # Find exact device with label persistence ext4
        for line in blkid_all.splitlines():
            if 'LABEL="persistence"' in line and 'TYPE="ext4"' in line:
                pdev = line.split(":", 1)[0].strip()
                print(f"Found existing persistence partition: {pdev}")
                mount_and_write_conf(pdev)
                print("Done. Reboot and choose: Live system (persistence)")
                return

    # If we have <3 partitions, create partition 3
    if len(parts) < 3:
        print(f"Creating persistence partition on {disk} (filling remaining free space)...")
        create_partition3(disk)

    # Now ensure partition 3 exists
    p3 = partition_path(disk, 3)
    if not os.path.exists(p3):
        # kernel may not have re-read yet
        wait_for_kernel()
    if not os.path.exists(p3):
        raise RuntimeError(f"Expected {p3} to exist but it doesn't. Try unplug/replug USB and rerun.")

    print(f"Formatting {p3} as ext4 label=persistence...")
    ensure_ext4_persistence(p3)

    print(f"Writing persistence.conf to {p3}...")
    mount_and_write_conf(p3)

    print("All set.")
    print("Reboot and choose: Live system (persistence)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
