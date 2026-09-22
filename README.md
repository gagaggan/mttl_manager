# FlaskFarm MTTL-W01 Manager

MTTL-W01 로컬 백엔드를 FlaskFarm에서 안전하게 확인하고 관리하기 위한 플러그인입니다.

## 현재 범위 (0.2.0)

- 로컬 MTTL 백엔드 URL 설정
- `GET /api/health` 상태 확인
- MTTL 웹 UI 바로가기
- 내부 API 주소와 외부 NPM 웹 UI 주소 분리 지원
- API 주소 자체에도 HTTPS NPM 도메인 사용 가능
- URL 내 자격증명·경로·쿼리 차단
- Home Assistant MQTT 설정 조회·연결 테스트·저장·Discovery 동기화
- MTTL 관리자 암호와 MQTT 암호를 FlaskFarm DB에 저장하지 않는 일회성 전달

다음 기능은 의도적으로 아직 포함하지 않습니다.

- 멀티탭 프로비저닝
- 펌웨어 생성 및 OTA
- 릴레이 또는 전원 제어
- Home Assistant/Mosquitto 사용자 자동 생성
- MTTL 백엔드 설치·삭제

## 설치 예정 환경

- FlaskFarm: VM 103 `ubuntu-ff`
- MTTL 백엔드: `/opt/mttl-up`의 독립 Docker Compose 프로젝트
- 기본 백엔드 주소: `http://127.0.0.1:8080`

MTTL 백엔드와 이 플러그인은 별도로 배포합니다. 플러그인 장애가 백엔드 통신에 영향을 주지 않도록 직접적인 프로세스 종속성을 만들지 않습니다.

## 개발

```bash
python -m pytest -q
```

실제 배포 전 제공 ZIP의 `README.md`, `deploy.sh`, Docker Compose 구성과 API를 검토하고, 확인된 API만 단계적으로 연결합니다.

MQTT 전용 사용자는 Home Assistant에서 한 번 생성해야 합니다. 플러그인은 HA 관리자 토큰을 보관하지 않으며, 생성된 계정을 MTTL 백엔드에 연결하는 작업만 수행합니다. MQTT 암호는 MTTL 백엔드의 암호화 저장소에 보관되고 FlaskFarm 설정 DB에는 저장되지 않습니다.
