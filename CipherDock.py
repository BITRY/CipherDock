#!/usr/bin/env python3
"""
CipherDock.py - Final LUKS Container Manager (created by MRy+o1):
 - Runs as root (sudo).
 - cryptsetup calls are done as root in this script.
 - Mount calls are done as normal user (USERNAME from config) with `sudo -u`.
 - After mount, we parse output from `udisksctl mount` and chown the mount path
   so the user can read/write if it's an ext4 filesystem owned by root.

Steps:
 1) Edit config.py to match your device, container dir, normal user, etc.
 2) sudo python3 CipherDock.py
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

# If your user environment needs special variables for `udisksctl` to see the session, set them:
EXTRA_ENV = {
    # "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
    # "XDG_RUNTIME_DIR": "/run/user/1000",
    # "DISPLAY": ":0",
}

# -------------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------------
logging.basicConfig(
    filename=CONFIG["LOG_FILE"],
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

class PasswordDialog(tk.Toplevel):
    """Dialog for passphrase input, with optional confirmation."""
    def __init__(self, parent, title="Enter Passphrase", confirm=False):
        super().__init__(parent)
        self.title(title)
        self.confirm = confirm
        self.passphrase = None
        self.grab_set()  # modal

        ttk.Label(self, text="Passphrase:").pack(padx=10, pady=(10,0), anchor="w")
        self.entry_pass = ttk.Entry(self, show="*", width=30)
        self.entry_pass.pack(padx=10, pady=5)
        self.entry_pass.focus_set()

        if self.confirm:
            ttk.Label(self, text="Confirm Passphrase:").pack(padx=10, pady=(10,0), anchor="w")
            self.entry_confirm = ttk.Entry(self, show="*", width=30)
            self.entry_confirm.pack(padx=10, pady=5)
        else:
            self.entry_confirm = None

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=5)

        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()//2) - (self.winfo_width()//2)
        y = parent.winfo_rooty() + (parent.winfo_height()//2) - (self.winfo_height()//2)
        self.geometry(f"+{x}+{y}")

    def _on_ok(self):
        p1 = self.entry_pass.get()
        if self.confirm:
            p2 = self.entry_confirm.get()
            if p1 != p2:
                messagebox.showerror("Error", "Passphrases do not match.")
                return
        self.passphrase = p1
        self.destroy()

    def _on_cancel(self):
        self.passphrase = None
        self.destroy()

def ask_passphrase(parent, title="Enter Passphrase", confirm=False):
    dlg = PasswordDialog(parent, title, confirm)
    parent.wait_window(dlg)
    return dlg.passphrase

# -------------------------------------------------------------------------
# MAIN APPLICATION
# -------------------------------------------------------------------------
class SecureContainerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure LUKS Container Manager (V5)")

        # If not root, cryptsetup calls might fail
        if os.geteuid() != 0:
            messagebox.showwarning(
                "Privilege Warning",
                "Please run this script as root (sudo) for cryptsetup operations."
            )

        self.partition_device = CONFIG["PARTITION_DEVICE"]
        self.container_dir    = CONFIG["CONTAINER_DIRECTORY"]
        self.default_size     = CONFIG["DEFAULT_CONTAINER_SIZE"]
        self.username         = CONFIG["USERNAME"]

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_exit)
        logging.info("App started (V5).")

        self._startup_cleanup_check()

    def _build_ui(self):
        frm_info = ttk.LabelFrame(self, text="Partition & Container Directory")
        frm_info.pack(padx=10, pady=10, fill='x')

        ttk.Label(frm_info, text=f"Partition: {self.partition_device}").pack(padx=5, pady=5, anchor="w")
        ttk.Label(frm_info, text=f"Container Dir: {self.container_dir}").pack(padx=5, pady=5, anchor="w")
        ttk.Label(frm_info, text=f"Mount as user: {self.username}").pack(padx=5, pady=5, anchor="w")

        ops = ttk.LabelFrame(self, text="Operations")
        ops.pack(padx=10, pady=10, fill='x')

        ttk.Button(ops, text="Create Container", command=self.create_container).pack(side='left', padx=5, pady=5)
        ttk.Button(ops, text="List Containers", command=self.list_containers).pack(side='left', padx=5, pady=5)
        ttk.Button(ops, text="Mount Container", command=self.mount_container).pack(side='left', padx=5, pady=5)
        ttk.Button(ops, text="Unmount Container", command=self.unmount_container).pack(side='left', padx=5, pady=5)

    # ---------------------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------------------
    def create_container(self):
        if not self._verify_container_dir_on_partition():
            return

        name = self._ask_for_string("Container Name", "Enter a container name (e.g. my_data):")
        if not name:
            return

        size_str = self._ask_for_string(
            "Container Size",
            f"Enter container size (e.g. 500M, 2G)\nDefault: {self.default_size}",
            default=self.default_size
        )
        if not size_str:
            return

        luks_pass = ask_passphrase(self, "LUKS Passphrase", confirm=True)
        if not luks_pass:
            return

        container_path = os.path.join(self.container_dir, f"{name}.img")
        if os.path.exists(container_path):
            messagebox.showerror("Error", f"Container file already exists:\n{container_path}")
            return

        # Check free space
        if not self._check_free_space(self.container_dir, size_str):
            return

        confirm = messagebox.askyesno(
            "Confirm",
            f"Create new LUKS container:\nFile: {container_path}\nSize: {size_str}\n\nProceed?"
        )
        if not confirm:
            return

        try:
            # 1) truncate
            subprocess.run(["truncate", "-s", size_str, container_path], check=True)

            # 2) luksFormat
            cmd_format = ["cryptsetup", "-q", "luksFormat", "--type", "luks2", container_path]
            subprocess.run(cmd_format, input=luks_pass+"\n", text=True, check=True)

            # 3) open
            mapper_name = f"{name}_mapper"
            subprocess.run(["cryptsetup", "open", container_path, mapper_name],
                           input=luks_pass+"\n", text=True, check=True)

            dev_mapper = f"/dev/mapper/{mapper_name}"

            # 4) mkfs.ext4
            subprocess.run(["mkfs.ext4", dev_mapper], check=True)
            # label with container name
            subprocess.run(["e2label", dev_mapper, name], check=True)

            # 5) close
            subprocess.run(["cryptsetup", "close", mapper_name], check=True)

            messagebox.showinfo("Success", f"Created container:\n{container_path}")
            logging.info(f"Created container {container_path}, size={size_str}")
        except subprocess.CalledProcessError as e:
            err = f"Failed to create container:\n{e}"
            messagebox.showerror("Error", err)
            logging.error(err)

    # ---------------------------------------------------------------------
    # LIST
    # ---------------------------------------------------------------------
    def list_containers(self):
        if not self._verify_container_dir_on_partition():
            return
        if not os.path.isdir(self.container_dir):
            messagebox.showerror("Error", f"Container directory not found:\n{self.container_dir}")
            return

        all_files = os.listdir(self.container_dir)
        containers = [f for f in all_files if f.endswith(".img") or f.endswith(".luks")]
        if containers:
            messagebox.showinfo("Containers Found", "\n".join(containers))
        else:
            messagebox.showinfo("Containers Found", "No container files found.")

    # ---------------------------------------------------------------------
    # MOUNT
    # ---------------------------------------------------------------------
    def mount_container(self):
        """
        1) pick container
        2) passphrase
        3) cryptsetup open as root
        4) mount as normal user => parse output, chown the mount dir
        """
        if not self._verify_container_dir_on_partition():
            return

        containers = self._get_container_files()
        if not containers:
            messagebox.showinfo("No Containers", "No container files found to mount.")
            return

        cfile = self._ask_user_choice("Select Container to Mount", containers)
        if not cfile:
            return

        base_name = os.path.splitext(cfile)[0]
        open_maps = self._detect_open_mappers()
        if f"{base_name}_mapper" in open_maps:
            messagebox.showwarning("Already Open", f"Container '{base_name}' is already open. Unmount it first.")
            return

        luks_pass = ask_passphrase(self, f"LUKS Passphrase for {cfile}", confirm=False)
        if not luks_pass:
            return

        container_path = os.path.join(self.container_dir, cfile)
        confirm = messagebox.askyesno(
            "Confirm",
            f"Mount container:\n{container_path}\n\nProceed?"
        )
        if not confirm:
            return

        mapper_name = f"{base_name}_mapper"
        dev_mapper = f"/dev/mapper/{mapper_name}"

        env = os.environ.copy()
        env.update(EXTRA_ENV)

        try:
            # 1) cryptsetup open as root
            subprocess.run(["cryptsetup", "open", container_path, mapper_name],
                           input=luks_pass+"\n", text=True, check=True)

            # 2) mount as normal user => parse the output
            mount_proc = subprocess.run(
                ["sudo", "-u", self.username, "udisksctl", "mount", "-b", dev_mapper],
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            stdout = mount_proc.stdout.strip()
            logging.info(f"udisksctl mount output: {stdout}")

            # The output usually: "Mounted /dev/mapper/foo at /run/media/USERNAME/foo."
            mount_path = None
            if " at " in stdout:
                after_at = stdout.split(" at ", 1)[1]
                # Remove trailing period if present
                mount_path = after_at.replace(".", "").strip()

            if mount_path and os.path.isdir(mount_path):
                # 3) chown to <username>
                subprocess.run(["chown", "-R", f"{self.username}:{self.username}", mount_path], check=True)
                messagebox.showinfo("Success", f"Mounted {cfile} at:\n{mount_path}\nChowned to {self.username} for R/W.")
                logging.info(f"Mounted {container_path}, chowned {mount_path} to {self.username}.")
            else:
                messagebox.showwarning(
                    "Mount Path Not Found",
                    f"Mount likely succeeded, but couldn't parse path from:\n{stdout}"
                )

        except subprocess.CalledProcessError as e:
            err = f"Mount failed:\n{e}\n\nOutput:\n{e.output}"
            messagebox.showerror("Error", err)
            logging.error(err)

    # ---------------------------------------------------------------------
    # UNMOUNT
    # ---------------------------------------------------------------------
    def unmount_container(self):
        open_maps = self._detect_open_mappers()
        if not open_maps:
            messagebox.showinfo("No Open Containers", "No container mappers are open.")
            return

        mapper_choice = self._ask_user_choice("Select Container to Unmount", open_maps)
        if not mapper_choice:
            return

        dev_mapper = f"/dev/mapper/{mapper_choice}"
        confirm = messagebox.askyesno(
            "Confirm Unmount",
            f"Unmount & close:\n{dev_mapper}\n\nProceed?"
        )
        if not confirm:
            return

        env = os.environ.copy()
        env.update(EXTRA_ENV)

        try:
            # unmount as user
            subprocess.run(["sudo", "-u", self.username, "udisksctl", "unmount", "-b", dev_mapper],
                           check=True, env=env)
            # close as root
            subprocess.run(["cryptsetup", "close", mapper_choice], check=True)

            messagebox.showinfo("Success", f"Unmounted & closed {mapper_choice}")
            logging.info(f"Unmounted & closed {mapper_choice}")
        except subprocess.CalledProcessError as e:
            err = f"Failed to unmount:\n{e}"
            messagebox.showerror("Error", err)
            logging.error(err)

    # ---------------------------------------------------------------------
    # STARTUP CLEANUP
    # ---------------------------------------------------------------------
    def _startup_cleanup_check(self):
        leftover = self._detect_open_mappers()
        if not leftover:
            return

        msg = "Found leftover open containers:\n\n" + "\n".join(leftover)
        msg += "\n\nClose them now?"
        do_cleanup = messagebox.askyesno("Startup Cleanup", msg)
        if not do_cleanup:
            return

        env = os.environ.copy()
        env.update(EXTRA_ENV)

        for mapper in leftover:
            dev_mapper = f"/dev/mapper/{mapper}"
            subprocess.run(["sudo", "-u", self.username, "udisksctl", "unmount", "-b", dev_mapper],
                           check=False, env=env)
            subprocess.run(["cryptsetup", "close", mapper], check=False)
            logging.info(f"Closed leftover mapper {mapper}")

    # ---------------------------------------------------------------------
    # EXIT CLEANUP
    # ---------------------------------------------------------------------
    def _on_exit(self):
        leftover = self._detect_open_mappers()
        if leftover:
            msg = "Still-open containers:\n\n" + "\n".join(leftover)
            msg += "\n\nUnmount + close them now?"
            do_cleanup = messagebox.askyesno("Clean Exit", msg)
            if do_cleanup:
                env = os.environ.copy()
                env.update(EXTRA_ENV)
                for mapper in leftover:
                    dev_mapper = f"/dev/mapper/{mapper}"
                    subprocess.run(["sudo", "-u", self.username, "udisksctl", "unmount", "-b", dev_mapper],
                                   check=False, env=env)
                    subprocess.run(["cryptsetup", "close", mapper], check=False)
                    logging.info(f"Auto-closed leftover mapper {mapper}")

        logging.info("Exiting application (V5).")
        self.destroy()

    # ---------------------------------------------------------------------
    # HELPER METHODS
    # ---------------------------------------------------------------------
    def _detect_open_mappers(self):
        mapper_dir = "/dev/mapper"
        if not os.path.isdir(mapper_dir):
            return []
        entries = os.listdir(mapper_dir)
        leftover = [m for m in entries if m.endswith("_mapper") and m != "control"]
        return leftover

    def _verify_container_dir_on_partition(self):
        cdir = self.container_dir
        part_dev = self.partition_device

        if not os.path.exists(cdir):
            try:
                os.makedirs(cdir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create container directory:\n{e}")
                return False

        # parse /proc/mounts for part_dev
        mountpoints = []
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                dev, mntp = parts[0], parts[1]
                if dev == part_dev:
                    mountpoints.append(mntp)

        if not mountpoints:
            messagebox.showerror(
                "Error",
                f"{part_dev} is not mounted.\nPlease mount it before using this app."
            )
            return False

        real_cdir = os.path.realpath(cdir)
        is_ok = any(
            os.path.commonpath([mnt, real_cdir]) == mnt
            for mnt in mountpoints
        )
        if not is_ok:
            messagebox.showerror(
                "Error",
                f"The container directory ({cdir}) is not on {part_dev}.\nAborting."
            )
            return False

        return True

    def _ask_for_string(self, title, prompt, default=""):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.grab_set()

        ttk.Label(dlg, text=prompt).pack(padx=10, pady=10, anchor="w")
        var = tk.StringVar(value=default)
        entry = ttk.Entry(dlg, textvariable=var, width=30)
        entry.pack(padx=10, pady=5)
        entry.focus_set()

        result = [None]
        def on_ok():
            val = var.get().strip()
            result[0] = val
            dlg.destroy()

        def on_cancel():
            result[0] = None
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

        self._center_window(dlg)
        self.wait_window(dlg)
        return result[0]

    def _ask_user_choice(self, title, options):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.grab_set()

        ttk.Label(dlg, text="Choose from the list:").pack(padx=10, pady=10)
        var = tk.StringVar()
        combo = ttk.Combobox(dlg, textvariable=var, values=options, state="readonly", width=50)
        combo.pack(padx=10, pady=5)
        combo.current(0)

        result = [None]
        def on_ok():
            result[0] = var.get()
            dlg.destroy()

        def on_cancel():
            result[0] = None
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

        self._center_window(dlg)
        self.wait_window(dlg)
        return result[0]

    def _center_window(self, win):
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width()//2) - (win.winfo_width()//2)
        y = self.winfo_rooty() + (self.winfo_height()//2) - (win.winfo_height()//2)
        win.geometry(f"+{x}+{y}")

    def _get_container_files(self):
        if not os.path.isdir(self.container_dir):
            return []
        all_files = os.listdir(self.container_dir)
        return sorted([f for f in all_files if f.endswith(".img") or f.endswith(".luks")])

    def _check_free_space(self, directory, size_str):
        size_bytes = self._parse_size_to_bytes(size_str)
        if size_bytes is None:
            messagebox.showerror("Error", f"Invalid size format: {size_str}")
            return False

        try:
            df_out = subprocess.check_output(["df", "--block-size=1", directory], text=True)
            lines = df_out.strip().split("\n")
            if len(lines) < 2:
                return True
            cols = lines[1].split()
            if len(cols) < 5:
                return True
            available = int(cols[3])
            if size_bytes > available:
                messagebox.showerror(
                    "Error",
                    f"Not enough free space.\nRequested: {size_str}\nAvailable: {available} bytes."
                )
                return False
        except Exception as e:
            logging.warning(f"Could not parse free space: {e}")
        return True

    @staticmethod
    def _parse_size_to_bytes(s):
        s = s.strip().upper()
        mult = 1
        if s.endswith("G"):
            mult = 1024**3
            s = s[:-1]
        elif s.endswith("M"):
            mult = 1024**2
            s = s[:-1]
        elif s.endswith("K"):
            mult = 1024
            s = s[:-1]
        try:
            val = float(s)
        except ValueError:
            return None
        return int(val * mult)

def main():
    app = SecureContainerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
