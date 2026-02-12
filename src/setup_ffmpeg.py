import os
import sys
import shutil
import zipfile
import urllib.request
import ssl
import time

# Switch to GitHub Release (BtbN) for potentially faster speed + progress bar support
# Using the GPL shared build (smaller) or static? Static is safer.
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
TARGET_FILE = "ffmpeg.exe"

def report_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = downloaded * 100 / total_size
        sys.stdout.write(f"\rDownloading: {percent:.1f}% ({downloaded // 1024 // 1024} MB / {total_size // 1024 // 1024} MB)")
        sys.stdout.flush()
    else:
        sys.stdout.write(f"\rDownloading: {downloaded // 1024 // 1024} MB")

def download_ffmpeg():
    print(f"Downloading FFmpeg from GitHub (BtbN)...")
    
    zip_path = "ffmpeg.zip"
    
    # Create unverified context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        # urlretrieve supports progress callback
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook=report_progress)
        print("\nDownload complete.")
    except Exception as e:
        print(f"\nDownload failed: {e}")
        return False

    print("Extracting ffmpeg.exe...")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            ffmpeg_path = None
            for name in z.namelist():
                if name.endswith("bin/ffmpeg.exe"):
                    ffmpeg_path = name
                    break
            
            if ffmpeg_path:
                with z.open(ffmpeg_path) as source, open(TARGET_FILE, "wb") as target:
                    shutil.copyfileobj(source, target)
                print(f"Extracted {TARGET_FILE} successfully.")
            else:
                print("Could not find bin/ffmpeg.exe in the zip.")
                return False
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False
    finally:
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                print("Cleaned up zip file.")
            except:
                pass

    return True

if __name__ == "__main__":
    if os.path.exists(TARGET_FILE):
        print(f"{TARGET_FILE} already exists.")
        # Optional: check size or version
    else:
        if download_ffmpeg():
            print("\nFFmpeg setup complete! You can now run the app.")
        else:
            print("\nFFmpeg setup failed. Please download it manually from https://github.com/BtbN/FFmpeg-Builds/releases")
