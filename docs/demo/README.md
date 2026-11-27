# 시연 영상

| 파일 | 내용 |
| --- | --- |
| [시연영상_LED_ON.mp4](시연영상_LED_ON.mp4) | 손가락으로 LED를 가리킨 뒤 엄지 위 → Raspberry Pi(`pi-led-01`) LED 켜짐 |
| [시연영상_LED_OFF.mp4](시연영상_LED_OFF.mp4) | 손가락으로 LED를 가리킨 뒤 엄지 아래 → LED 꺼짐 |
| [핵심유스케이스_웹화면.mp4](핵심유스케이스_웹화면.mp4) | 웹 대시보드 화면 녹화: 기기 선택·ON/OFF, 도움 요청 생성·확인·처리 완료, 제어 이력 |

- 실제 시연 구성: 노트북 웹캠 Edge → AI 서버(Docker) → Mosquitto → Raspberry Pi 4 `pi_led_agent`(GPIO 17 LED)
- 웹 화면 녹화는 별도 더미 환경에서 손동작 인식 결과만 대본으로 넣고, 의도 판단 이후(MQTT 명령, 기기 ACK, 웹 실시간 반영)는 실제 서버 코드로 처리했다.
- 저장소 `.gitignore`가 `*.mp4`를 제외하므로 이 폴더의 영상은 `git add -f`로 추가했다.
