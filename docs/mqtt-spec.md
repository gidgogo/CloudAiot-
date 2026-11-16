# MQTT 명세

API 프로세스의 `server/iot/mqtt_client.py`가 다음 v1 Topic을 QoS 1로 사용한다.

```text
aiot/v1/{home_id}/{device_id}/cmd
aiot/v1/{home_id}/{device_id}/ack
aiot/v1/{home_id}/{device_id}/state
aiot/v1/{home_id}/{device_id}/status
```

- `cmd`: `CONFIRMED` 상태의 ON/OFF 의도만 Raspberry Pi LED agent로 발행하며 Retain하지 않는다.
- `ack`: 명령 이력을 완료·실패로 갱신하고 성공 시 기기 상태를 함께 반영한다.
- `state`: 현재 ON/OFF 상태를 반영한다.
- `status`: ONLINE/OFFLINE 및 LWT 상태를 반영한다.
- Topic의 `v1`, `home_id`, `device_id`와 페이로드의 버전·기기 ID가 다르면 사용하지 않는다.
- 명령 발행 후 2초 안에 ACK가 없으면 `ACK_TIMEOUT`으로 기록한다.
- MQTT 수신과 WebSocket EventHub는 API 워커 1개 안에서 실행한다.

현재 시연 수신자는 `pi-led-01` Raspberry Pi LED agent다. Pi는 `cmd`를 구독해 GPIO의 저전압 LED를 ON/OFF하고, 동일한 `device_id`로 `ack`, retain `state`, retain `status`를 발행한다. ESP32·릴레이·220V 부하는 현재 범위에 포함하지 않는다.

계약 파일은 `shared/schemas/v1/mqtt-command.schema.json`과
`shared/schemas/v1/mqtt-ack.schema.json`이다.

