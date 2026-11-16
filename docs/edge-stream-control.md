# 영상 송출 켜기/끄기: 물리 버튼 · 상태 LED · MQTT 원격 제어

SSH로 접속하지 않고도 라즈베리파이의 영상 송출(`edge.main --stream`)을 켜고 끄는 방법을 정리한다.

```
                         ┌──────── edge.stream_control (systemd, 부팅 시 자동 실행) ────────┐
[버튼 GPIO26] ──누름──▶  │  StreamPanel ──toggle──▶ ProcessSwitch ──▶ python -m edge.main  │──WebSocket──▶ AI 서버
[LED  GPIO22] ◀─상태──   │      ▲                        ▲                                  │
                         │      └──── LED 동기화 ─── CommandHandler ◀── MQTT cmd            │
                         └──────────────────────────────────┬───────────────────────────────┘
웹/서버 ──cmd(ON/OFF)──▶ Mosquitto ◀──── ack · state(retain) · status(LWT) ─────────┘
```

- 송출은 MQTT 기기 하나(`edge-stream-01`)로 취급한다. 조명·선풍기 릴레이와 **같은 규격**(공통 인터페이스 11장)이라 서버는 기기 제어와 똑같이 `ON`/`OFF` 명령만 보내면 된다.
- 버튼으로 바꾼 상태도 `state` Topic에 retain으로 발행하므로, 웹에서 항상 현재 상태를 볼 수 있다.

## 1. 배선

준비물: 택트 스위치 1개, LED 1개, 330Ω 저항 1개, 점퍼선(암-수), 브레드보드

| 부품 | 연결 | 물리 핀 번호 |
|---|---|---|
| 버튼 한쪽 다리 | GPIO 26 | 37번 |
| 버튼 반대쪽 다리 | GND | 39번 |
| LED 긴 다리(+, 애노드) | GPIO 22 | 15번 |
| LED 짧은 다리(−, 캐소드) → 330Ω 저항 | GND | 14번 또는 39번 |

```
 3.3V [ 1] [ 2] 5V
      ...
GPIO22 [15]─────▶|─[330Ω]──[14] GND        (LED: 긴 다리가 GPIO 쪽)
      ...
GPIO26 [37]──[버튼]──[39] GND               (풀업 내장, 외부 저항 불필요)
```

- **반드시 전원을 끄고** 배선한다.
- 저항 없이 LED를 연결하면 LED와 GPIO 핀이 손상될 수 있다.
- GPIO 17과 27은 조명·선풍기 릴레이(`light-01`, `fan-01`)용으로 예약되어 있어서 피했다.
- 버튼은 내부 풀업을 쓰므로 GPIO와 GND 사이에 버튼만 연결하면 된다.

## 2. LED 의미

| LED | 상태 |
|---|---|
| 켜짐 | 송출 중 |
| 꺼짐 | 정지 |
| 빠르게 깜빡임 | 송출 프로세스가 스스로 종료됨(카메라 연결 불량, 서버 설정 오류 등). 버튼을 누르면 다시 시작한다 |

네트워크가 끊기는 경우는 `edge.main`이 스스로 재접속하므로 LED가 켜진 상태로 유지된다.

## 3. 설정

```bash
cp edge/config.example.yaml edge/config.yaml
```

`edge/config.yaml`의 `stream_control` 절을 수정한다. 송출 설정(서버 주소, 토큰, 카메라)과 같은 파일이다.

```yaml
stream_control:
  device_id: edge-stream-01
  button_pin: 26
  led_pin: 22
  initial_state: OFF    # ON이면 부팅하자마자 송출
  remote:
    enabled: false      # MQTT 원격 ON/OFF. 5장 참고
```

송출 설정(서버 주소, 토큰, 카메라)은 `edge/config.yaml`이나 환경변수를 따른다. 비밀값은 저장소 루트의 `.env`에 둔다. 이 파일은 `.gitignore` 대상이다.

```bash
# ~/CloudAiot-/.env
EDGE_TOKEN=...
EDGE_SERVER_URL=ws://<서버 주소>:8000
EDGE_CAMERA_SOURCE=picamera2
```

## 4. 부팅 시 자동 실행 (systemd)

```bash
bash deploy/systemd/install-edge-stream-control.sh   # cloudaiot-edge 서비스 등록 + 시작 (gpiozero/lgpio는 시스템 패키지 사용)
```

| 명령 | 용도 |
|---|---|
| `systemctl status cloudaiot-edge` | 상태 확인 |
| `journalctl -u cloudaiot-edge -f` | 실시간 로그 (송출 로그도 여기에 함께 나온다) |
| `sudo systemctl restart cloudaiot-edge` | 설정을 바꾼 뒤 재시작 |
| `sudo systemctl disable --now cloudaiot-edge` | 자동 실행 해제 |

## 5. 원격 제어 (MQTT, 선택)

기본값은 꺼져 있다(`stream_control.remote.enabled: false`). 켜면 송출을 MQTT 기기 하나(`edge-stream-01`)처럼
`ON`/`OFF` 명령으로 제어한다. 필요한 패키지는 `paho-mqtt`이며(`pip install -e ".[edge-control]"`), 브로커 주소는
`remote.mqtt.host` 또는 `EDGE_MQTT_HOST`로 정한다.

> **합의 필요**: 이 기기를 웹에 일반 기기로 등록하면 제스처로 카메라가 꺼질 수 있다. 원격 ON/OFF를 일반 기기 Topic과
> 분리할지, 기기 종류로 제스처 대상에서 제외할지 서버·웹 담당과 정한 뒤 켠다.

웹 대시보드가 붙기 전에는 `send_command`로 서버와 같은 명령을 보내 확인한다.

```bash
python -m edge.stream_control.send_command edge-stream-01 ON  --host <브로커 주소>
python -m edge.stream_control.send_command edge-stream-01 OFF --host <브로커 주소>
```

로컬 브로커는 `docker compose up -d mosquitto`로 띄운다.

| Topic | 내용 |
|---|---|
| `aiot/v1/home-01/edge-stream-01/cmd` | 서버 → Pi. `action`: `ON`/`OFF`, `source`: `WEB` 등 |
| `aiot/v1/home-01/edge-stream-01/ack` | Pi → 서버. 처리 결과 |
| `aiot/v1/home-01/edge-stream-01/state` | 현재 송출 상태 (retain). 버튼으로 바꿔도 발행된다 |
| `aiot/v1/home-01/edge-stream-01/status` | `ONLINE`/`OFFLINE` (LWT) |

### 웹·서버 담당이 할 일

- `server/iot/mqtt_client.py`의 `publish_command()`로 `device_id="edge-stream-01"`, `source=WEB` 명령을 보내는 REST 엔드포인트와 웹 버튼을 추가한다.
- `state` Topic을 구독해 대시보드에 송출 상태를 표시한다(서버의 state·ack 구독은 아직 구현되지 않음).

## 6. 검증 기록 (2026-11-15)

라즈베리파이 4B와 카메라 모듈 3, 맥의 Mosquitto와 Mock 프레임 서버로 확인했다.

- 원격 `ON` → ACK `OK` → 송출 시작, 약 9fps, ACK 타임아웃 0 → LED 핀(GPIO22) HIGH
- 원격 `OFF` → ACK `OK` → 송출 프로세스가 정상 종료(final metrics 출력) → LED LOW
- `state`(OFF)와 `status`(ONLINE)가 retain으로 남는 것을 확인했다.
- 버튼 입력은 실제 부품 없이 단위 테스트(`tests/edge/stream_control/test_switch_panel.py`)로만 확인했다.
- 위 기록은 `iot_agent/`에 있던 시점의 코드로 확인했다. `edge/stream_control/`로 옮긴 뒤에는 Pi 실물 시험을 다시 해야 한다.

---

## 부록: 핫스팟을 비상 Wi-Fi로 등록

처음 가는 장소처럼 등록된 Wi-Fi가 없을 때, 휴대폰 핫스팟으로 파이에 접속해 그 장소의 Wi-Fi를 추가한다.

1. 휴대폰 핫스팟 이름과 비밀번호를 확인한다. 아이폰은 "호환성 최대화"를 켠다(2.4GHz).
2. 파이가 지금 연결된 상태에서 등록한다. 비밀번호는 본인이 직접 입력한다.

```bash
sudo nmcli connection add type wifi con-name hotspot ifname wlan0 ssid "<핫스팟 이름>" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<핫스팟 비밀번호>" \
  connection.autoconnect yes connection.autoconnect-priority 10
nmcli connection show
```

3. 시험: 집 Wi-Fi를 잠시 끄거나(또는 파이를 공유기에서 멀리) 핫스팟을 켠 뒤, 맥도 핫스팟에 연결하고 `ssh pi`를 실행한다.
4. 새 장소의 Wi-Fi 추가 (핫스팟으로 접속한 상태에서):

```bash
sudo nmcli device wifi connect "<와이파이 이름>" password "<비밀번호>"
```

- `autoconnect-priority`가 높을수록 먼저 연결한다. 집 Wi-Fi를 우선하려면 집 Wi-Fi를 더 높게 둔다.
- 학교처럼 기기 간 통신을 막는 Wi-Fi에서는 같은 Wi-Fi여도 `ssh pi`가 안 될 수 있다. 이때는 핫스팟을 쓴다.
