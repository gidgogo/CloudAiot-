# Raspberry Pi MQTT LED Agent

`pi_led_agent`는 Raspberry Pi에서 MQTT v1 명령을 받아 GPIO의 저전압 LED를 ON/OFF하고 ACK, state, status(LWT)를 발행한다.

자세한 배선·설정·실행·검증 절차는 [`docs/pi-led-agent.md`](../docs/pi-led-agent.md)를 따른다. `edge/` 카메라 전송 프로그램은 이 패키지의 범위가 아니며 수정하지 않는다.
