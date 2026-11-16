# Raspberry Pi MQTT LED Agent

## 목적과 범위

`pi_led_agent/`는 Raspberry Pi에서 CloudAIoT MQTT v1 `cmd` Topic을 구독해 GPIO의 **저전압 LED**를 ON/OFF한다. 처리 결과는 `ack`, 현재 LED 상태는 retain `state`, 접속 상태는 retain `status`와 LWT로 API 서버에 알린다.

이 agent는 `edge/` 카메라 전송 프로그램과 독립적이다. 두 프로그램은 같은 Pi에서 실행할 수 있으나, `edge/`의 코드와 설정을 변경하지 않는다. ESP32, 릴레이, 220V 부하는 이 시연 범위에 포함하지 않는다.

## 배선

Pi 전원을 끈 상태에서만 배선한다.

```text
BCM GPIO 17 ── 저항(예: 220~330 ohm) ── LED 긴 다리(Anode)
GND         ───────────────────────── LED 짧은 다리(Cathode)
```

- 기본 GPIO 번호는 물리 핀 번호가 아닌 **BCM 17**이다.
- LED와 저항은 반드시 함께 사용한다.
- 배선·극성이 다르면 `LED_GPIO_PIN`, `LED_ACTIVE_LOW`를 환경설정에서 맞춘다.
- 릴레이와 220V 부하는 연결하지 않는다.

## MQTT 계약

`home-01`, `pi-led-01`을 사용할 때의 Topic은 다음과 같다.

```text
aiot/v1/home-01/pi-led-01/cmd      # 서버 -> Pi
aiot/v1/home-01/pi-led-01/ack      # Pi -> 서버, QoS 1, retain false
aiot/v1/home-01/pi-led-01/state    # Pi -> 서버, QoS 1, retain true
aiot/v1/home-01/pi-led-01/status   # Pi -> 서버, QoS 1, retain true / LWT
```

Pi는 `schema_version == "1.0"`, 자신의 `device_id`, `ON`/`OFF`, 5초 유효시간, `command_id` 중복 여부를 검사한다. 실행하지 못한 명령도 가능한 경우 ERROR, EXPIRED 또는 DUPLICATE ACK로 응답한다. 시스템 시간이 명백히 설정되지 않았으면 LED를 제어하지 않는다.

## 설정과 실행

Pi에서 의존성을 설치한다.

```bash
cd ~/CloudAI
python -m pip install -e '.[pi-led-agent,dev]'
```

템플릿을 복사해 실제 Mosquitto를 실행하는 Linux 데스크톱의 같은 네트워크 IP를 넣는다. `mosquitto`와 `localhost`는 Pi에서 브로커 주소로 사용하지 않는다.

```bash
cp pi_led_agent/.env.example pi_led_agent/.env
set -a
. pi_led_agent/.env
set +a
python -m pi_led_agent.main
```

`MQTT_HOST`에는 예를 들어 `192.168.137.10`처럼 Linux 데스크톱의 실제 LAN·핫스팟 IP를 설정한다. `MQTT_HOME_ID`, `MQTT_DEVICE_ID`는 서버·웹의 등록 기기와 같아야 한다. `.env`에는 비밀번호가 들어갈 수 있으므로 Git에 추가하지 않는다.

## 검증

GPIO 배선을 확인하기 전에는 코드 시험만 수행한다.

```bash
python -m pytest tests/pi_led_agent -q
```

브로커와 서버를 실행한 뒤에는 웹에서 `pi-led-01` 기기를 등록하고, ON/OFF 제어 후 LED 상태·ACK·WebSocket 대시보드 반영을 확인한다.
