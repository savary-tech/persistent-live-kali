# persistent-live-kali

Save your self the long read by watching this video instead ---> 

Turn a freshly flashed Kali Linux Live USB into a persistent Kali environment automatically.

No fdisk
No parted
No manual mounting
No persistence headaches

This script detects the USB, creates the persistence partition, formats it as ext4, writes `persistence.conf`, and prepares the drive so Kali actually remembers your files and tools across reboots.

---

## What it does

After you flash Kali Live ISO to a USB, the system normally boots in a temporary session where everything is erased after reboot.

This tool:

1. Detects the Kali USB drive
2. Creates a third partition using remaining free space
3. Formats it as `ext4` labeled `persistence`
4. Writes the required configuration file
5. Prepares the drive for **Live system (persistence)** boot mode

---

## Requirements

You must run this on Linux:

* Kali Linux (recommended)
* Ubuntu / Debian
* WSL2 (works)

You need root privileges.

```
python3
lsblk
parted
mkfs.ext4
mount
blkid
udevadm
```

Most Linux systems already have these installed.

---

## Install

Clone the repo:

```
git clone https://github.com/savary-tech/persistent-live-kali/
cd persistent-live-kali
```

Make executable:

```
chmod +x kali_persistence_setup.py
```

---

## Usage

### 1) Flash Kali to USB first

Use Rufus (DD mode) or dd:

```
sudo dd if=kali-linux-xxxx-live-amd64.iso of=/dev/sdX bs=4M status=progress
sync
```

Replace `/dev/sdX` with your USB device.

---

### 2) Run the script

```
sudo python3 kali_persistence_setup.py
```

If multiple drives are connected:

```
lsblk
sudo python3 kali_persistence_setup.py --device /dev/sdb
```

---

## After running

Reboot and select:

```
Live system (persistence)
```

---

## Test persistence

Inside Kali:

```
touch works.txt
reboot
```

If `works.txt` still exists → persistence works.

---

## Safety

The script tries to auto-detect the USB drive, but disk operations are dangerous.

**Always verify the device before running:**

```
lsblk
```

Do NOT run on your main disk.

---

## Troubleshooting

### Persistence option missing

You booted wrong mode.
Select: `Live system (persistence)`

---

### Changes not saving

Partition label must be `persistence`
File must contain:

```
/ union
```

---

### Script refuses device

Specify it manually:

```
sudo python3 kali_persistence_setup.py --device /dev/sdX
```

---

## Why this exists

Kali persistence setup normally requires manual partitioning and several commands.
People frequently mess it up or accidentally wipe the wrong disk.

This tool makes it a one-command setup.
