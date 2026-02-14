# 프로젝트 개요 및 구조

## 1. 프로젝트 목표
Vision Pro, iPhone, iPad 등 iOS 기기의 화면을 **RTMP** 프로토콜을 이용해 Windows 가상 카메라로 스트리밍하는 로컬 네트워크 기반 솔루션입니다.  
사용자는 PRISM Live Studio 등 RTMP 스트리밍 앱을 통해 영상을 전송하고, Windows에서는 가상 카메라 드라이버를 통해 Zoom, OBS, Teams 등 다양한 애플리케이션에서 웹캠으로 사용할 수 있습니다.

## 2. 핵심 아키텍처
```
[ iOS/Vision Pro ] → RTMP 스트림 → FFmpeg 디코딩 → VirtualCamera (DirectShow) → Windows 앱
```
- **RTMP 스트림**: `src/protocols/rtmp.py` 에서 구현, 포트 2935 기본.
- **SRT / WebRTC**: `src/protocols/srt.py`, `src/protocols/webrtc.py` 로 대체 가능.
- **디코더**: `src/decoder.py` 가 FFmpeg 로부터 프레임을 받아 `numpy.ndarray` 로 변환.
- **스트리밍 파이프라인**: `src/streaming_pipeline.py` 가 `ConnectionManager`, `ProtocolAdapter`, `FrameDecoder` 를 연결하고 상태·헬스 이벤트를 관리.
- **가상 카메라**: `src/virtual_camera.py` 가 Windows 가상 카메라 드라이버와 연동해 프레임을 출력.
- **시스템 트레이 UI**: `src/tray.py` 와 `src/settings_dialog.py` 로 사용자가 시작·중지·설정 등을 제어.

## 3. 주요 모듈 및 역할
| 모듈 | 주요 클래스 / 함수 | 역할 |
|------|-------------------|------|
| `config.py` | `AppConfig` | 설정값(포트, 프로토콜, 재연결 옵션 등) 정의 |
| `config_manager.py` | `ConfigurationManager` | JSON 기반 설정 파일 로드·저장·검증 |
| `connection_manager.py` | `ConnectionManager` | 연결 상태(`ConnectionState`)·헬스(`ConnectionHealth`) 관리 |
| `decoder.py` | `FrameDecoder` | FFmpeg 출력 스트림을 프레임 단위로 읽고 오류 카운트 관리 |
| `protocols/rtmp.py` | `RTMPAdapter` | RTMP 서버 프로세스 실행·URL·설명 제공 |
| `protocols/srt.py` | `SRTAdapter` | SRT 프로토콜 지원 (대체 옵션) |
| `protocols/webrtc.py` | `WebRTCAdapter` | WebRTC 기반 스트리밍 (미구현 테스트) |
| `streaming_pipeline.py` | `StreamingPipeline` | 전체 파이프라인 조립·시작·정지·콜백 연결 |
| `virtual_camera.py` | `VirtualCameraOutput` | 가상 카메라 드라이버에 프레임 전송 |
| `tray.py` | `TrayApp` | 시스템 트레이 아이콘·메뉴·상태 표시 |
| `setup_driver.py` | `main()` | 가상 카메라 드라이버 설치·레지스트리·방화벽 설정 |
| `setup_ffmpeg.py` | `download_ffmpeg()` | FFmpeg 바이너리 자동 다운로드·설치 |

## 4. 테스트 커버리지
- 각 프로토콜 어댑터, 연결 매니저, 디코더, 파이프라인에 대한 **unit test** 가 `src/test_*.py` 에 존재.
- 테스트는 `pytest` 로 실행 가능하며, 모의 객체(`MockProtocolAdapter`) 를 사용해 비동기 흐름을 검증.

## 5. 현재 파악된 개선/보완 작업
| 번호 | 작업 내용 | 우선순위 |
|------|-----------|----------|
| 1 | `virtual_camera.py` 와 `decoder.py` 에 **docstring** 추가 (API 사용법 명시) | 높음 |
| 2 | `README.md` 에 **설치 가이드**(FFmpeg 설치, 드라이버 설치, 실행 방법) 보강 | 높음 |
| 3 | `test_webrtc_adapter.py` 에 **WebRTC 테스트** 추가 (실제 네트워크 환경 검증) | 중간 |
| 4 | `test_srt_adapter.py` 에 **SRT edge‑case 테스트**(대역폭 제한, 재연결) 추가 | 중간 |
| 5 | `streaming_pipeline.py` 의 **메모리 사용 최적화**(프레임 버퍼 관리) | 중간 |
| 6 | `decoder.py` 에 **성능 로깅**(프레임 처리 시간, 오류 카운트) 추가 | 낮음 |
| 7 | `setup_driver.py` 에 **Windows 버전별 방화벽/권한 체크** 강화 | 낮음 |

## 6. 작업 진행 방법 (TODO 리스트)

- [ ] `virtual_camera.py` 와 `decoder.py` 에 함수·클래스별 docstring 작성
- [ ] `README.md` 에 FFmpeg·드라이버 설치 절차와 실행 예시 추가
- [ ] `test_webrtc_adapter.py` 에 실제 연결·스트림 테스트 케이스 구현
- [ ] `test_srt_adapter.py` 에 대역폭·재연결 시나리오 테스트 추가
- [ ] `streaming_pipeline.py` 의 프레임 버퍼 로직을 검토·리팩터링
- [ ] `decoder.py` 에 `logging` 모듈을 이용한 성능 로그 출력 구현
- [ ] `setup_driver.py` 에 Windows 10/11 별 권한/방화벽 설정 로직 보강

---

위 내용은 현재 코드베이스를 기반으로 한 **프로젝트 구조 파악** 및 **향후 진행해야 할 작업**을 정리한 것입니다. 필요에 따라 세부 구현을 진행해 주세요.  

*문서가 `docs/project_overview.md` 에 저장되었습니다.*