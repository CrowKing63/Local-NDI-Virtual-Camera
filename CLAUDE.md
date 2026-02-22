# CLAUDE.md

## 프로젝트 개요

Windows에서 Vision Pro/iPhone/iPad를 가상 웹캠으로 사용할 수 있게 해주는 애플리케이션.
iOS 기기에서 RTMP/SRT/WebRTC로 스트리밍된 영상을 H.264 디코딩 후 Unity Capture DirectShow 드라이버를 통해 가상 카메라로 출력한다.

**OS 요구사항:** Windows 10/11 전용 (DirectShow, Windows Firewall, Registry 의존)

## 주요 명령어

```bash
# 실행
python -m src
python src/main.py

# 테스트
pytest src/test_*.py -v

# 환경 검증
python src/verify_env.py

# 드라이버 설치 (관리자 권한 필요)
python src/setup_driver.py

# FFmpeg 설치
python src/setup_ffmpeg.py

# 의존성 설치
pip install -r requirements.txt
```

## 아키텍처

### 핵심 컴포넌트

| 파일 | 역할 |
|------|------|
| `src/main.py` | 애플리케이션 오케스트레이터, 전체 라이프사이클 관리 |
| `src/connection_manager.py` | 상태 머신, 헬스 모니터링, 자동 재연결 |
| `src/decoder.py` | H.264 → FFmpeg → RGB24 프레임 디코딩 |
| `src/virtual_camera.py` | Unity Capture 드라이버로 프레임 출력 |
| `src/streaming_pipeline.py` | 전체 스트리밍 파이프라인 통합 |
| `src/tray.py` | 시스템 트레이 UI |
| `src/config_manager.py` | JSON 설정 영속성 (`%APPDATA%/LocalVirtualCamera/config.json`) |
| `src/server.py` | HTTP 정보 서버 (QR코드, 접속 URL) |

### 프로토콜 어댑터 (`src/protocols/`)

Factory 패턴으로 프로토콜을 생성하며, `ProtocolAdapter` 추상 베이스를 통해 교체 가능.

| 어댑터 | 포트 | 비고 |
|--------|------|------|
| RTMP | 2935 | 기본값, FFmpeg RTMP 서버 래핑 |
| SRT | 9000 | 저지연 대안 |
| WebRTC | 8080 | P2P, aiortc 기반 |

HTTP 정보 서버: 포트 8000

### 패턴

- **Factory Pattern** — `protocols/factory.py`로 어댑터 생성
- **Strategy Pattern** — 프로토콜 어댑터 교체
- **State Machine** — ConnectionManager 내 연결 상태 추적
- **Asyncio + Threading** — 비동기 네트워크 + UI 스레드 분리

## 외부 의존성

- **FFmpeg** — 비디오 코덱, RTMP 서버 (자동 다운로드)
- **UnityCapture** — 가상 카메라 DirectShow 필터 드라이버 (`driver/`)
- **Python 3.10+**

## 테스트

- 테스트 파일: `src/test_*.py` (13개 모듈)
- 실제 네트워크 없이 테스트하기 위한 Mock 어댑터 포함
- `pytest` + `pytest-asyncio` 사용

## 설정 값 기본값

```python
protocol = ProtocolType.RTMP
rtmp_port = 2935
srt_port = 9000
http_port = 8000
frame_width = 1280
frame_height = 720
fps = 30
auto_reconnect = True
max_reconnect_attempts = 10
```

## 주의사항

- 드라이버 설치(`setup_driver.py`)는 관리자 권한 필요
- Windows Firewall 규칙 자동 등록 포함
- 새 프로토콜 추가 시 `protocols/base.py`의 `ProtocolAdapter`를 상속하고 `protocols/factory.py`에 등록
- `decoder.py`는 FFmpeg 바이너리 경로를 `config.py`에서 감지
