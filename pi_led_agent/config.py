"""Environment-based configuration for the Raspberry Pi LED agent."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _integer(env: Mapping[str, str], name: str, default: int, *, minimum: int = 0) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _boolean(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True, slots=True)
class PiLedAgentConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_home_id: str
    mqtt_device_id: str
    mqtt_client_id: str
    mqtt_keepalive_sec: int
    mqtt_tls: bool
    mqtt_username: str | None
    mqtt_password: str | None
    led_gpio_pin: int
    led_active_low: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "PiLedAgentConfig":
        env = os.environ if env is None else env
        username = env.get("MQTT_USERNAME", "").strip() or None
        password = env.get("MQTT_PASSWORD", "") or None
        return cls(
            mqtt_host=_required(env, "MQTT_HOST"),
            mqtt_port=_integer(env, "MQTT_PORT", 1883, minimum=1),
            mqtt_home_id=_required(env, "MQTT_HOME_ID"),
            mqtt_device_id=_required(env, "MQTT_DEVICE_ID"),
            mqtt_client_id=env.get("MQTT_CLIENT_ID", "pi-led-agent-01").strip() or "pi-led-agent-01",
            mqtt_keepalive_sec=_integer(env, "MQTT_KEEPALIVE_SEC", 30, minimum=1),
            mqtt_tls=_boolean(env, "MQTT_TLS"),
            mqtt_username=username,
            mqtt_password=password,
            led_gpio_pin=_integer(env, "LED_GPIO_PIN", 17, minimum=0),
            led_active_low=_boolean(env, "LED_ACTIVE_LOW"),
        )
