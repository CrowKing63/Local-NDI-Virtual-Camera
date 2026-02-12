import os
import sys
import socket
import shutil

# Add src to path to import config
sys.path.append(os.getcwd())

try:
    from src import config
except ImportError:
    print("Could not import src.config. Make sure you are in the project root.")
    sys.exit(1)

print("--- Environment Verification ---")
print(f"CWD: {os.getcwd()}")

# 1. Check FFmpeg
print("\n[1] Checking FFmpeg via config...")
ffmpeg_bin = config.FFMPEG_BIN
print(f"config.FFMPEG_BIN: {ffmpeg_bin}")

if ffmpeg_bin:
    if os.path.exists(ffmpeg_bin):
        size = os.path.getsize(ffmpeg_bin)
        print(f"File exists. Size: {size / 1024 / 1024:.2f} MB")
        if size < 1000:
            print("WARNING: File is too small! Download might have failed.")
    else:
        print("ERROR: File path defined but does not exist.")
else:
    print("ERROR: config.FFMPEG_BIN is None. FFmpeg not found in search paths.")
    # Check local ffmpeg.exe specifically
    local_ffmpeg = os.path.abspath("ffmpeg.exe")
    print(f"Checking local {local_ffmpeg}: {os.path.exists(local_ffmpeg)}")

# 2. Check Port 10000
print("\n[2] Checking Port 10000...")
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 10000))
        print("Port 10000 is free (Bound successfully).")
except OSError as e:
    print(f"Port 10000 is BUSY/LOCKED: {e}")

# 3. Check Driver
print("\n[3] Checking Unity Capture Driver...")
dll_path = os.path.join(os.getcwd(), "driver", "UnityCaptureFilter64.dll")
print(f"Looking for DLL: {dll_path}")
if os.path.exists(dll_path):
    print("DLL found.")
else:
    print("DLL NOT found.")

print("\n--- End Verification ---")
