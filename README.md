# Local Virtual Camera (Vision Pro / iOS → Windows)

Turn your Vision Pro, iPhone, or iPad into a high-quality virtual webcam for Windows. 
**No SSL certificates, no HTTPS setup, and low-latency streaming.**

Using **RTMP**, **SRT**, or **WebRTC** protocols, this tool provides a robust video bridge that works instantly on your local network.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Virtual Camera Driver
Run as Administrator:
```bash
python src/setup_driver.py
```

### 3. Install FFmpeg (if not in PATH)
```bash
python src/setup_ffmpeg.py
```

### 4. Run the App
```bash
python -m src
```

### 5. Start Streaming
1. Right-click the tray icon → **Start Streaming**
2. Copy the RTMP/SRT URL shown in the menu
3. On iOS/Vision Pro, use **PRISM Live Studio** or **Larix Broadcaster**

### 6. Use in Windows Apps
- Open Zoom, OBS, Teams, or any video app
- Select **"Local Virtual Camera"** (or Unity Video Capture) as your webcam

## 📱 iOS/Vision Pro Setup

### PRISM Live Studio (Recommended)
1. Download from App Store (Free)
2. Open → Tap **Ready** → **Custom RTMP**
3. Add new destination:
   - **Name**: Local VCam
   - **URL**: `rtmp://192.168.x.x:2935/live`
   - **Stream Key**: `stream`
4. Tap **Go Live**

### Larix Broadcaster
1. Download from App Store
2. Connections → Add
   - **URL**: `rtmp://192.168.x.x:2935/live`
   - **Stream Name**: `stream`

## 🔌 Supported Protocols

| Protocol | Port | Best For |
|----------|------|----------|
| RTMP | 2935 | Broad compatibility |
| SRT | 9000 | Lower latency, better error correction |
| WebRTC | 8080 | Ultra-low latency (requires aiortc) |

Switch protocols via tray menu: **Protocol** → Select RTMP/SRT/WebRTC

## 🛠️ Requirements
- **Windows 10/11**
- **Python 3.10+**
- **Network**: Both devices on same Wi-Fi/LAN

## 🔧 Troubleshooting

### Connection Issues
- **Firewall**: Allow ports 2935 (RTMP), 9000 (SRT), 8000 (HTTP) in Windows Firewall
- **Driver not found**: Run `python src/setup_driver.py` as Administrator

### Performance
- Use 5GHz Wi-Fi for best results
- Close other bandwidth-intensive applications

### Driver Installation Failed
1. Download UnityCapture driver manually from GitHub
2. Place `UnityCaptureFilter64.dll` in the `driver/` folder
3. Run `python src/setup_driver.py` again

## 📜 Why RTMP?
Previous versions used WebCodecs, but Safari's SSL requirements made setup cumbersome. RTMP provides:
- **Zero Configuration**: No Root CAs or profile trust settings
- **Native Performance**: Uses device hardware encoder
- **Universal**: Works with any RTMP-supporting app

## 📁 Project Structure
```
src/
├── main.py           # Application entry point
├── decoder.py        # H.264 → RGB frame decoder
├── virtual_camera.py # Virtual camera output
├── protocols/        # RTMP, SRT, WebRTC adapters
├── tray.py          # System tray UI
├── config*.py       # Configuration
└── setup_*.py       # Installation scripts
```

## 🧪 Testing
```bash
# Verify environment
python src/verify_env.py

# Run unit tests
pip install pytest pytest-asyncio
pytest src/test_*.py -v
```
