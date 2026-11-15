#!/usr/bin/env bash
# 라즈베리파이에서 IoT 에이전트(송출 버튼·LED·MQTT 원격 제어)를 부팅 시 자동 실행되게 등록한다.
#
#   저장소 루트에서: bash deploy/systemd/install-iot-agent.sh
#
# 현재 사용자와 저장소 경로, .venv 파이썬으로 서비스 파일을 만든다.
# 비밀값(EDGE_TOKEN, IOT_MQTT_PASSWORD 등)은 저장소 루트의 .env 에 둔다(.gitignore 대상).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$REPO/.venv/bin/python"
UNIT=/etc/systemd/system/cloudaiot-iot.service

[ -x "$PY" ] || { echo "가상환경이 없습니다: $PY (docs/raspberry-pi-setup.md 5장 참고)"; exit 1; }
[ -f "$REPO/iot_agent/config.yaml" ] || { echo "iot_agent/config.yaml 이 없습니다. config.example.yaml 을 복사해 수정하세요."; exit 1; }

sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=CloudAIoT IoT agent (stream button/LED, MQTT control)
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$REPO
EnvironmentFile=-$REPO/.env
ExecStart=$PY -m iot_agent.main
# 정지 시 SIGTERM → 에이전트가 송출 프로세스를 정리하고 OFFLINE을 남긴다
KillMode=mixed
TimeoutStopSec=20
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cloudaiot-iot
echo "등록 완료. 상태: systemctl status cloudaiot-iot   로그: journalctl -u cloudaiot-iot -f"
