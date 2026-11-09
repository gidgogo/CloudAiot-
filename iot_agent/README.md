# IoT 제어 Pi 에이전트

ESP32 대신 **라즈베리파이**로 조명·선풍기 릴레이를 제어할 때 쓰는 에이전트입니다.
서버와는 MQTT로만 통신하고, [공통 인터페이스 규격 v1.0](../docs/interfaces/common-interface-spec-v1.0.md) 11장(Topic·페이로드·QoS)을 ESP32와 똑같이 따릅니다.
그래서 **서버 코드(`server/iot/`)는 바꾸지 않습니다.** 메시지 형식은 `shared/types.py`(`MqttCommand`, `MqttAck`, `DeviceStateMessage`, `DeviceStatusMessage`)와 `shared/mqtt_topics.py`를 그대로 씁니다.

```
AI 서버 ──cmd──▶ Mosquitto ──▶ [IoT 제어 Pi: iot_agent] ─GPIO─▶ 릴레이
   ▲                                  │
   └──────── ack / state / status ────┘
```

카메라 Pi(`edge/`)와 같은 Pi에서 돌려도 되지만, edge와 섞지 말고 별도 프로세스(서비스)로 실행합니다.

## 설치와 실행

```bash
python -m pip install -r iot_agent/requirements.txt
cp iot_agent/config.example.yaml iot_agent/config.yaml   # home_id, device_id, 핀 수정
```

```bash
python -m iot_agent.main            # 라즈베리파이 + 실제 릴레이
python -m iot_agent.main --mock     # 노트북: 릴레이 대신 로그, 시간 동기화 검사 생략
```

로컬에서 확인하는 방법 (Mosquitto는 `docker compose up mosquitto`):

```bash
mosquitto_sub -h localhost -t 'aiot/v1/home-01/#' -v
```

```bash
mosquitto_pub -h localhost -q 1 -t aiot/v1/home-01/light-01/cmd -m "{\"schema_version\":\"1.0\",\"command_id\":\"$(uuidgen)\",\"correlation_id\":\"\",\"device_id\":\"light-01\",\"action\":\"ON\",\"issued_at_ms\":$(date +%s)000,\"expires_at_ms\":$(( $(date +%s) + 5 ))000,\"source\":\"WEB\"}"
```

## 설정

| 키 | 설명 |
| --- | --- |
| `agent.home_id` | Topic의 `{home_id}`. 서버와 같아야 함 |
| `agent.agent_id` | MQTT client_id 접두사. 실제 client_id는 `{agent_id}-{device_id}` |
| `mqtt.*` | 브로커 주소·TLS·계정. `IOT_MQTT_HOST`, `IOT_MQTT_USERNAME`, `IOT_MQTT_PASSWORD` 환경변수가 우선 |
| `time_sync.required` | `true`면 NTP 동기화 전에는 명령을 실행하지 않음 (규격 11.7) |
| `devices.{device_id}.pin` | BCM 핀 번호 |
| `devices.{device_id}.active_high` | 릴레이 모듈이 HIGH에서 켜지면 `true`. 흔한 모듈은 LOW에서 켜지므로 기본 `false` |
| `devices.{device_id}.initial_state` | 시작 시 상태. 안전을 위해 `OFF` 권장 |

## 동작

명령 하나를 받으면 `command_handler.py`가 아래 순서로 처리하고 ACK를 1개 발행합니다.

| 순서 | 검사 | 실패 시 ACK `result` / `error_code` |
| --- | --- | --- |
| 1 | JSON, `command_id` 존재 | ACK 없이 폐기 (누구에게 답할지 모름) |
| 2 | `schema_version == "1.0"` | `ERROR` / `UNSUPPORTED_VERSION` |
| 3 | 필수 필드, `action`이 `ON`·`OFF` | `ERROR` / `INVALID_SCHEMA` |
| 4 | `device_id`가 이 Topic의 기기 | `ERROR` / `DEVICE_NOT_FOUND` |
| 5 | NTP 동기화 | `ERROR` / `TIME_NOT_SYNCED` (릴레이 동작 안 함) |
| 6 | `expires_at_ms` 이전인지 | `EXPIRED` / `COMMAND_EXPIRED` |
| 7 | 처음 보는 `command_id`인지 | `DUPLICATE` / `COMMAND_DUPLICATE` (릴레이 재동작 금지) |
| 8 | 릴레이 동작 | 성공 `OK`, GPIO 오류 `ERROR` / `INTERNAL_ERROR` |

- ACK의 `state`에는 처리 후 현재 상태를 넣습니다.
- 상태가 실제로 바뀌면 `state` Topic에 retain으로 발행합니다.
- 접속 직후 `status`=`ONLINE`과 현재 `state`를 retain으로 발행합니다.
- 비정상 종료 시에는 브로커가 LWT로 `OFFLINE`을 발행합니다. 정상 종료(SIGINT/SIGTERM) 시에는 에이전트가 직접 `OFFLINE`을 남깁니다.
- LWT는 연결당 1개뿐이라 **기기마다 MQTT 연결을 따로** 맺습니다.
- 연결이 끊기면 paho가 1~30초 간격으로 재접속합니다.
- 처리한 `command_id`는 기기별로 최근 1024개를 메모리에 기억합니다. 재시작하면 지워지지만, 5초 유효시간 때문에 오래된 재전송은 `EXPIRED`로 걸러집니다.

## systemd 등록 (라즈베리파이)

`/etc/systemd/system/cloudaiot-iot.service` (경로·사용자는 환경에 맞게 수정):

```ini
[Unit]
Description=CloudAIoT IoT controller
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/CloudAiot-
ExecStart=/home/pi/CloudAiot-/.venv/bin/python -m iot_agent.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now cloudaiot-iot
```

## 파일

- `main.py`: 진입점, 기기별 에이전트 시작·종료
- `config.py`, `config.example.yaml`: 설정과 환경변수 우선 적용
- `relay.py`: `GpioRelay`(gpiozero)와 `MockRelay`
- `command_handler.py`: cmd 검증·만료·중복·실행·ACK 생성 (MQTT와 분리, 단위 테스트 대상)
- `mqtt_agent.py`: 기기 하나의 MQTT 연결, LWT, 구독·발행
- `time_sync.py`: `timedatectl`로 NTP 동기화 확인

## 남은 일 / 합의 필요

- **`TIME_NOT_SYNCED` 오류 코드**는 규격 12.2에 없습니다. 규격 11.7은 "오류 ACK"만 정했기 때문에 통합 담당과 코드 이름을 합의해야 합니다.
- 실제 릴레이 모듈의 active-high/low 여부와 핀 번호는 장비가 확정된 뒤 정합니다.
- 서버 쪽 `server/iot/`에는 아직 ack·state·status를 **구독하는 코드가 없습니다.** 파싱 함수만 있습니다. 서버 담당이 구현해야 합니다.
- 규격 문서와 SAD의 "ESP32" 표기를 "IoT 제어부(ESP32 또는 Raspberry Pi)"로 바꿀지 팀이 결정해야 합니다.
