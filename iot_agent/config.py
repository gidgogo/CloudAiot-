"""IoT 제어 Pi 설정. 개인 설정(config.yaml)이 없으면 동봉된 예제를 사용한다."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shared.config import load_yaml

DEFAULT_PATH = Path(__file__).with_name("config.yaml")
EXAMPLE_PATH = Path(__file__).with_name("config.example.yaml")

MQTT_HOST_ENV = "IOT_MQTT_HOST"
MQTT_USERNAME_ENV = "IOT_MQTT_USERNAME"
MQTT_PASSWORD_ENV = "IOT_MQTT_PASSWORD"


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = DEFAULT_PATH if DEFAULT_PATH.exists() else EXAMPLE_PATH
    config = load_yaml(path)
    mqtt = config.setdefault("mqtt", {})
    # 환경변수가 있으면 설정 파일보다 우선한다. 비밀번호는 파일에 쓰지 않는 것을 권장한다.
    mqtt["host"] = os.environ.get(MQTT_HOST_ENV) or mqtt.get("host", "localhost")
    mqtt["username"] = os.environ.get(MQTT_USERNAME_ENV) or mqtt.get("username")
    mqtt["password"] = os.environ.get(MQTT_PASSWORD_ENV) or mqtt.get("password")
    if not config.get("devices"):
        raise ValueError("devices must define at least one device")
    if not config.get("agent", {}).get("home_id"):
        raise ValueError("agent.home_id is required")
    return config
