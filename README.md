# persistent-live-kali

Automatically enables persistence on a Kali Linux Live USB.

This script finds the `ext4` partition labeled **persistence**, mounts it, creates the required `persistence.conf` file, and safely unmounts the drive.

No manual mounting
No guessing device names
No editing files inside DiskGenius or hex editors

---

## What problem this solves

After creating a Kali persistent partition, Kali still will NOT save data unless the file below exists:

```
persistence.conf
```

with exactly:

```
/ union
```

Creating this file is usually annoying because Windows cannot write to ext4 partitions.

This tool automates it completely.

---

## Requirements

Run on Linux:

* Kali Linux (recommended)
* Ubuntu / Debian
* WSL2 (works perfectly)

Root privileges required.

Tools required (normally preinstalled):

```
blkid
findmnt
mount
umount
sync
python3
```

---

## Installation

Clone the repo:

```
git clone https://github.com/yourusername/kali-persistence-conf.git
cd kali-persistence-conf
```

Make executable:

```
chmod +x make_persistence_conf.py
```

---

## Usage

### Automatic mode (recommended)

Plug in your Kali USB and run:

```
sudo ./make_persistence_conf.py
```

The script will:

1. Find the ext4 partition labeled `persistence`
2. Mount it
3. Create `persistence.conf`
4. Unmount safely

---

### Specify device manually

If multiple drives exist:

```
sudo ./make_persistence_conf.py --device /dev/sdb3
```

---

### Custom mount location

```
sudo ./make_persistence_conf.py --mount /mnt/my_usb
```

---

## After running

Reboot your computer and boot the USB using:

```
Live system (persistence)
```

---

## Verify persistence works

Inside Kali:

```
touch testfile
reboot
```

If `testfile` still exists after reboot → success.

---

## Safety

The script only writes a single small file and does NOT modify partitions.

It will refuse to run unless:

* the partition exists
* filesystem is ext4

---

## Troubleshooting

### Script says no persistence partition found

Your partition label must be:

```
persistence
```

Check with:

```
lsblk -f
```

---

### Kali still not saving data

You probably booted:

```
Live system
```

Instead of:

```
Live system (persistence)
```

---

## Why this exists

Windows cannot write to ext4 partitions.
Most persistence setup guides require manual mounting in Linux.

This tool reduces the final persistence setup step to a single command.

---

## License

MIT

---

If you want, I can also write a short repo description + tags so GitHub search actually surfaces it when people google “kali persistence not working”.
