"""서버·웹 대신 MQTT 제어 명령을 한 번 보내고 ACK를 기다리는 도구 (개발·데모용).

서버가 보내는 것과 같은 규격(공통 인터페이스 11.2)으로 발행하므로, 웹 대시보드가 붙기 전에
"원격으로 송출 켜기/끄기"를 확인할 수 있다.

    python -m iot_agent.send_command edge-stream-01 ON  --host <브로커 주소>
    python -m iot_agent.send_command edge-stream-01 OFF --host <브로커 주소>
"""
from __future__ import annotations

import argparse
import json
import sys
import threading

import paho.mqtt.client as mqtt

from shared.constants import ACK_TIMEOUT_MS, COMMAND_TTL_MS
from shared.mqtt_topics import ack_topic, command_topic, state_topic
from shared.types import CommandSource, IntentAction, MqttCommand, now_ms


def send(host: str, port: int, home_id: str, device_id: str, action: IntentAction, *,
         username: str | None = None, password: str | None = None) -> dict | None:
    issued = now_ms()
    command = MqttCommand(device_id=device_id, action=action, source=CommandSource.WEB,
                          issued_at_ms=issued, expires_at_ms=issued + COMMAND_TTL_MS)
    got_ack = threading.Event()
    ack: dict = {}

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(ack_topic(home_id, device_id), qos=1)
        client.publish(command_topic(home_id, device_id), json.dumps(command.as_dict()), qos=1, retain=False)

    def on_message(client, userdata, message):
        payload = json.loads(message.payload)
        if payload.get("command_id") == command.command_id:
            ack.update(payload)
            got_ack.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True, protocol=mqtt.MQTTv311)
    if username:
        client.username_pw_set(username, password)
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(host, port, keepalive=10)
    client.loop_start()
    try:
        # 규격 11.5: 서버는 2초 동안 ACK를 기다린다. 송출 프로세스 기동 시간을 감안해 조금 여유를 둔다.
        return ack if got_ack.wait(ACK_TIMEOUT_MS / 1000 + 3) else None
    finally:
        client.disconnect()
        client.loop_stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="MQTT 제어 명령 한 번 보내기 (서버·웹 대역)")
    parser.add_argument("device_id", help="예: edge-stream-01")
    parser.add_argument("action", choices=["ON", "OFF"])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--home-id", default="home-01")
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    ack = send(args.host, args.port, args.home_id, args.device_id, IntentAction(args.action),
               username=args.username, password=args.password)
    if ack is None:
        print(f"ACK 없음: {ack_topic(args.home_id, args.device_id)} 를 확인하세요 (에이전트 실행 여부, 브로커 주소)")
        sys.exit(1)
    print(f"ACK {ack['result']} state={ack['state']} error={ack.get('error_code')}")
    print(f"현재 상태는 {state_topic(args.home_id, args.device_id)} (retain) 에서도 확인할 수 있습니다.")
    sys.exit(0 if ack["result"] == "OK" else 2)


if __name__ == "__main__":
    main()
