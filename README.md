# CipherDock 🔒🚀  

**CipherDock** is a **lightweight, standalone** LUKS-based container manager written entirely in **Python**.  
It allows users to **create, mount, unmount, and manage encrypted storage containers** in a simple and efficient way.  
Designed for **privacy and security**, CipherDock ensures your sensitive data remains safe while being easy to access.

🔹 **Minimal & Efficient** – The entire program is contained within a **single script (`CipherDock.py`)**, plus a simple config file (`config.py`).  
🔹 **No heavy dependencies** – Uses **basic Python libraries** and standard Linux tools (cryptsetup, udisks2).  
🔹 **Requires `sudo`** – Creating, encrypting, and formatting LUKS containers needs **root privileges**.  
🔹 **Auto-Mount in Nautilus/Thunar** – Once unlocked, containers appear like removable drives. Ownership is automatically set so you can read/write as a normal user.

---

## 🚀 Features

<table>
  <tr>
    <td width="50%">
      <img src="https://github.com/BITRY/CipherDock/blob/main/splash.png" alt="CipherDock Logo" width="100%">
    </td>
    <td width="50%" valign="top">
      <ul>
        <li>🔐 <b>Secure</b> – Uses LUKS encryption for <i>strong, industry-standard security</i>.</li>
        <li>📦 <b>Container-based</b> – Store encrypted <code>.img</code> files on any external drive or system path.</li>
        <li>🖥️ <b>GUI Interface</b> – Simple <i>Tkinter-based UI</i> for creating and unlocking containers.</li>
        <li>🔄 <b>Auto-Mount</b> – Uses <i>UDisks2</i>, making unlocked containers <i>visible in Nautilus/Thunar</i> like a USB drive.</li>
        <li>👤 <b>User Access</b> – Ownership auto-adjusts so you can read/write as a normal user after mounting.</li>
        <li>🛠️ <b>Free-Space Check</b> – Prevents container creation if there is <i>not enough storage</i> available.</li>
        <li>🪚 <b>Auto Cleanup</b> – Detects <i>leftover mounts</i> and offers to clean them on startup or exit.</li>
        <li>📝 <b>Logging</b> – Stores logs in <code>/var/log/secure_container_app.log</code> for auditing.</li>
      </ul>
    </td>
  </tr>
</table>

---

## 👅 Installation

### **1️⃣ Prerequisites**
Ensure your system has the following:

- **Linux** (Ubuntu, Debian, Arch, Fedora, etc.)
- **Python 3.10+**
- **Minimal Dependencies**:  
    sudo apt-get update && sudo apt-get install -y cryptsetup udisks2 python3-tk

### **2️⃣ Clone the Repository**
    git clone https://github.com/BITRY/CipherDock.git
    cd CipherDock

### **3️⃣ Configure CipherDock**
Edit `config.py` to suit your environment (partition device, container directory, normal username, etc.):

    """
    Configuration for CipherDock (Minimal LUKS Container Manager)
    Edit these values to match your environment.
    """

    CONFIG = {
        # The partition device for your external drive (e.g., /dev/sdc1)
        "PARTITION_DEVICE": "/dev/sdc1",

        # Directory where encrypted containers will be stored
        "CONTAINER_DIRECTORY": "/media/user/external_drive/containers",

        # Default container size if not specified (e.g. "10G")
        "DEFAULT_CONTAINER_SIZE": "10G",

        # Log file path for the application
        "LOG_FILE": "/var/log/secure_container_app.log",

        # The normal user who owns the desktop session – needed for mounting
        "USERNAME": "your-username",
    }

🔹 **IMPORTANT**:  
- Set the **correct partition path** and **container directory** so your data is stored where you expect.  
- Update `"USERNAME"` to match **your** normal user.  
- If UDisks2 doesn’t properly mount in your session, you may need to set `DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR`, etc. in the script’s `EXTRA_ENV`.

---

## ▶️ Running CipherDock

You **must run the script as root** when creating or unlocking containers, because LUKS operations need root privileges:

    sudo python3 CipherDock.py

**Why `sudo`?**  
- `cryptsetup` (used for LUKS encryption) requires admin privileges.  
- Mounting a device sometimes needs root if permissions are restrictive.  

**After mounting**, the container is visible as a normal folder/drive to your desktop session. CipherDock automatically updates permissions so you can read/write as a normal user in Nautilus or Thunar.

---

## ❓ Troubleshooting

1. **Mounting fails or drive is not recognized?**  
   - Make sure the partition is **mounted** and `PARTITION_DEVICE` is correct.  
   - Check available drives with:
   
         lsblk

2. **Permission errors when running?**  
   - Ensure you used `sudo python3 CipherDock.py`.  
   - If the container directory on the partition belongs to root, fix ownership:
   
         sudo chown -R $USER:$USER /media/user/external_drive/

3. **Missing dependencies?**  
   - Reinstall required packages:
   
         sudo apt-get install --reinstall cryptsetup udisks2 python3-tk

4. **User session environment issues?**  
   - If `udisksctl` can’t access your session bus, set environment variables like `DBUS_SESSION_BUS_ADDRESS` or `XDG_RUNTIME_DIR` inside `EXTRA_ENV` in the script.

---

## 🔧 Uninstalling CipherDock

1. Remove the cloned folder:
   
       rm -rf ~/CipherDock

2. (Optional) Delete log files:
   
       sudo rm /var/log/secure_container_app.log

---

## 🔒 Important Notes on Security

- **Always unmount and close containers** when not actively using them.  
- **Never store encryption passwords** in the code or config files.  
- **Use strong passphrases** to protect your data.  
- **Regularly back up** your encrypted containers to prevent data loss.

---

## Example `CipherDock.py` (Optional)

Below is an **example** script that demonstrates how CipherDock might handle cryptsetup calls, session mounting, and auto-chown:

    #!/usr/bin/env python3
    """
    app_v5.py - Final LUKS Container Manager (two-file) that:
     - Runs as root (sudo).
     - cryptsetup calls are done as root in this script.
     - Mount calls are done as normal user (USERNAME from config) with `sudo -u`.
     - After mount, we parse output from `udisksctl mount` and chown the mount path
       so the user can read/write if it's an ext4 filesystem owned by root.

    Steps:
     1) Edit config.py to match your device, container dir, normal user, etc.
     2) sudo python3 app_v5.py
     3) Create container, mount container. Nautilus sees it at /run/media/<USERNAME>/<Label>.
     4) Ownership is automatically fixed so you can write to it in Nautilus.

    Note:
     - If your user session environment isn't recognized, you might pass DBUS_SESSION_BUS_ADDRESS, XDG_RUNTIME_DIR, etc.
       in an EXTRA_ENV dictionary below, so `udisksctl` truly runs in the user's session.
    """

    import os
    import sys
    import subprocess
    import logging
    import tkinter as tk
    from tkinter import ttk, messagebox

    # Import config
    from config import CONFIG

    # If your user session environment needs special variables (DBUS_SESSION_BUS_ADDRESS, etc.), set them:
    EXTRA_ENV = {
        # "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        # "XDG_RUNTIME_DIR": "/run/user/1000",
        # "DISPLAY": ":0",
    }

    logging.basicConfig(
        filename=CONFIG["LOG_FILE"],
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # [ Full example code omitted for brevity... ]
    # but it includes calls to cryptsetup, mount as normal user, auto-chown, etc.

---

💡 **Done!** Just run `sudo python3 CipherDock.py` after you’ve **configured** `config.py`, and enjoy seamless, secure LUKS container management.
