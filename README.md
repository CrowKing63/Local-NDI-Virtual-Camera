# Local RTMP Virtual Camera (Vision Pro / iOS → Windows)

Turn your Vision Pro, iPhone, or iPad into a high-quality virtual webcam for Windows. 
**No SSL certificates, no HTTPS setup, and low-latency streaming.**

Using the **RTMP** protocol, this tool provides a robust video bridge that works instantly on your local network.

## 🚀 Quick Start (RTMP Mode)

### 1. Windows Setup
1. **Install Virtual Camera Driver**: Run `python src/setup_driver.py`.
2. **Install FFmpeg**: Ensure FFmpeg is installed and in your PATH.
3. **Run the App**: `python -m src`.
4. **Start Streaming**: Right-click the tray icon and select **Start Streaming**. It will show your RTMP URL (e.g., `rtmp://192.168.x.x:2935/live/stream`).

### 2. Vision Pro / iOS Setup
1. Download **PRISM Live Studio** (Free) from the App Store.
2. Open PRISM Live → Tap **Ready** (Yellow button) → Tap **Custom RTMP**.
3. Tap **Add** (Add a new stream destination):
   - **Name**: Local VCam
   - **URL**: `rtmp://192.168.x.x:2935/live`
   - **Stream Key**: `stream`
4. Go back to the main screen and tap **Go Live** to start streaming.

### 3. Use in Windows
- Open Zoom, OBS, or Teams.
- Select **"Local Virtual Camera"** (or Unity Video Capture) as your webcam.

## 🛠️ Requirements
- **Windows 10/11**
- **Python 3.10+**
- **Larix Broadcaster** (or any RTMP app like OBS Camera).
- **Network**: Both devices must be on the same Wi-Fi/LAN.

## 🔧 Troubleshooting
- **Firewall**: If it doesn't connect, ensure Port **1935** (RTMP) and **8000** (Info) are allowed in Windows Firewall.
- **Latency**: Ensure you are on 5GHz Wi-Fi for the best experience.
- **Driver not found**: Run `python src/setup_driver.py` with Administrator privileges.

## 📜 Why RTMP?
Previous versions used a browser-based (WebCodecs) approach, but Safari's strict security requirements for SSL certificates made the setup extremely cumbersome. By switching to RTMP:
- **Zero Configuration**: No Root CAs or manual profile trust settings.
- **Native Performance**: Uses the device's native hardware encoder.
- **Universal**: Works with any app that supports RTMP.
