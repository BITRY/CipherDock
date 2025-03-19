# CipherDock 🔒🚀

![CipherDock Logo](https://raw.githubusercontent.com/BITRY/CipherDock/main/splash.png)

**CipherDock** is a secure LUKS-based container manager that allows users to **create, mount, unmount, and manage encrypted storage containers** seamlessly. Designed for **privacy and security**, CipherDock ensures your sensitive data remains safe while being easy to access when needed.

---

## 🚀 Features

- **🔐 Secure** – Uses LUKS encryption for **strong, industry-standard security**.
- **📦 Container-based** – Store encrypted `.img` files on any external drive or system path.
- **🖥️ GUI Interface** – Simple **Tkinter-based UI** for managing your secure storage.
- **🔄 Auto-Mount** – Automatically mounts using **UDisks2**, making it **visible in Nautilus** like a USB drive.
- **👤 User Access** – Mounted volumes are **readable & writable** for the logged-in user (no root access needed post-mount).
- **🛠️ Free-Space Check** – Prevents container creation if there is not enough storage available.
- **🧹 Auto Cleanup** – Detects **leftover mounts** and offers to clean them on startup or exit.
- **📝 Logging** – Keeps logs in `/var/log/secure_container_app.log`.

---

## 📥 Installation

### **1️⃣ Prerequisites**
Ensure your system has the following:

- **Linux** (Ubuntu, Debian, Arch, Fedora, etc.)
- **Python 3.10+**
- **Dependencies:**  
  Install required packages with:
  ```bash
  sudo apt-get update && sudo apt-get install -y cryptsetup udisks2 python3-tk
