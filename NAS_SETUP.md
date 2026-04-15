# NAS Setup Guide

Archive files (audio, artwork, database) live on the NAS so both the Windows
scraper machine and the Linux player machine share the same data without
duplicating hundreds of GB.

```
NAS IP:    192.168.1.30
Share:     usbshare1
Folder:    media/music/Communion After Dark/
```

---

## Windows — map the share as drive Z:

Open PowerShell **once** to create the persistent mapping:

```powershell
net use Z: \\PineNAS\usbshare1 /user:SynoAdmin /persistent:yes
```

Windows will prompt for the password.  The mapping survives reboots.

Then set the environment variables **permanently** for your user account
(no need to repeat this after a reboot):

```powershell
[System.Environment]::SetEnvironmentVariable(
    "CAD_ARCHIVE_DIR",
    "Z:\media\music\Communion After Dark\archive",
    "User"
)
[System.Environment]::SetEnvironmentVariable(
    "CAD_DATA_DIR",
    "Z:\media\music\Communion After Dark\data",
    "User"
)
```

Close and reopen any terminal after setting these.  Verify with:

```powershell
echo $env:CAD_ARCHIVE_DIR
```

---

## Linux — mount the share permanently via fstab

### 1. Install the SMB client

```bash
# Debian / Ubuntu / Mint
sudo apt install cifs-utils

# Arch
sudo pacman -S cifs-utils

# Fedora
sudo dnf install cifs-utils
```

### 2. Create the mount point

```bash
sudo mkdir -p /mnt/nas
```

### 3. Store credentials securely

Create a credentials file so your password isn't visible in `/etc/fstab`:

```bash
sudo nano /etc/nas-credentials
```

Paste these two lines (replace with your real password):

```
username=SynoAdmin
password=YOUR_SYNOLOGY_PASSWORD
```

Lock it down so only root can read it:

```bash
sudo chmod 600 /etc/nas-credentials
```

### 4. Add the fstab entry

```bash
sudo nano /etc/fstab
```

Add this line at the end (one line, no wrapping):

```
//PineNAS/usbshare1  /mnt/nas  cifs  credentials=/etc/nas-credentials,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,iocharset=utf8,nofail,_netdev  0  0
```

> **`nofail`** — system boots normally even if the NAS is offline.  
> **`_netdev`** — waits for the network before mounting (prevents race on boot).  
> **`uid=1000,gid=1000`** — your regular user owns the mounted files so the
> scraper and player can read/write without sudo.  Run `id` to confirm your
> uid/gid if you're unsure.

### 5. Test without rebooting

```bash
sudo mount -a
ls /mnt/nas/media/music/
# Should show: Communion After Dark
```

### 6. Set the environment variables

Copy `.env.example` to `.env` inside the repo (Linux version is already filled in):

```bash
cp .env.example .env
```

The Linux lines are already uncommented.  To make them permanent, add to
`~/.bashrc` (or `~/.zshrc`):

```bash
echo 'source ~/path/to/communion-after-dark/.env' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
echo $CAD_ARCHIVE_DIR
# /mnt/nas/media/music/Communion After Dark/archive
```

---

## Run the player on Linux pointing at the NAS

```bash
cd player

# One-time: install system deps
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
    gstreamer1.0-python3-plugin-loader \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-pulseaudio

# Run (env var sets the archive path automatically)
source ~/.bashrc
python -m cad_player.main

# Or pass the path explicitly without the env var:
python -m cad_player.main \
    --archive "/mnt/nas/media/music/Communion After Dark/archive" \
    --db "/mnt/nas/media/music/Communion After Dark/data/cad_archive.db"
```

---

## Run the scraper on either machine

```bash
cd scraper
pip install -r requirements.txt

# Make sure env vars are set first (source .env or set via PowerShell)
python main.py discover --all   # first run only
python main.py run --batch 10   # repeat until archive is complete
```

The scraper writes directly to the NAS.  Both machines share the same
`cad_archive.db` — don't run the scraper on both simultaneously.
