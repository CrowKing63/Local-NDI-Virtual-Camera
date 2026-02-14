"""
Setup script to:
1. Download and register Unity Capture virtual camera driver.
2. Add Windows Firewall rules for RTMP (2935), SRT (9000), and HTTP (8000) ports.

Run this script as Administrator once.
"""

import os
import sys
import shutil
import zipfile
import urllib.request
import subprocess
import ctypes

DRIVER_URL = "https://github.com/schellingb/UnityCapture/archive/refs/heads/master.zip"
DRIVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "driver")
# Filename in the repo is UnityCaptureFilter64.dll (not 64bit.dll)
DLL_NAME = "UnityCaptureFilter64.dll"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def download_driver():
    if not os.path.exists(DRIVER_DIR):
        os.makedirs(DRIVER_DIR)

    zip_path = os.path.join(DRIVER_DIR, "UnityCapture.zip")
    print(f"Downloading driver from {DRIVER_URL}...")
    try:
        urllib.request.urlretrieve(DRIVER_URL, zip_path)
    except Exception as e:
        print(f"Download failed: {e}")
        return False

    print("Extracting driver...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # We need Install/UnityCaptureFilter64bit.dll
            # The zip structure is UnityCapture-master/Install/...
            for file in zip_ref.namelist():
                if file.endswith(DLL_NAME):
                    source = zip_ref.open(file)
                    target_path = os.path.join(DRIVER_DIR, DLL_NAME)
                    with open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    print(f"Extracted {DLL_NAME} to {target_path}")
                    return target_path
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False
    return None


def register_dll(dll_path):
    print(f"Registering {dll_path}...")
    # regsvr32 /s (silent)
    try:
        subprocess.check_call(["regsvr32", "/s", dll_path])
        print("Driver registered successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Registration failed: {e}")
        return False


def add_firewall_rule():
    ports = [2935, 9000, 8000]  # RTMP, SRT, HTTP
    print(f"Adding firewall rules for ports {ports}...")

    for port in ports:
        cmd = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name=Local Virtual Camera (port {port})",
            "dir=in",
            "action=allow",
            "protocol=TCP",
            f"localport={port}",
            "profile=any",
        ]
        try:
            subprocess.run(
                [
                    "netsh",
                    "advfirewall",
                    "firewall",
                    "delete",
                    "rule",
                    f"name=Local Virtual Camera (port {port})",
                ],
                capture_output=True,
            )
            subprocess.check_call(cmd)
            print(f"Firewall rule added for port {port}!")
        except subprocess.CalledProcessError as e:
            print(f"Firewall rule failed for port {port}: {e}")
            return False
    return True


def main():
    if not is_admin():
        print("Requesting administrator privileges...")
        # Re-run the script with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        return

    print("--- Local Virtual Camera Setup ---")

    # 1. Driver
    dll_path = os.path.join(DRIVER_DIR, DLL_NAME)
    if not os.path.exists(dll_path):
        dll_path = download_driver()

    if dll_path and os.path.exists(dll_path):
        register_dll(dll_path)
    else:
        print("Could not find or download driver DLL.")

    # 2. Firewall
    add_firewall_rule()

    print("\nSetup complete. You can now run the application.")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
