import pytest

from pi_led_agent.config import PiLedAgentConfig


def test_config_reads_pi_agent_settings():
    config = PiLedAgentConfig.from_env({
        "MQTT_HOST": "192.168.1.10", "MQTT_PORT": "1884", "MQTT_HOME_ID": "home-01",
        "MQTT_DEVICE_ID": "pi-led-01", "LED_GPIO_PIN": "27", "LED_ACTIVE_LOW": "true",
    })
    assert config.mqtt_port == 1884
    assert config.led_gpio_pin == 27
    assert config.led_active_low


def test_config_requires_broker_and_identity():
    with pytest.raises(ValueError, match="MQTT_HOST"):
        PiLedAgentConfig.from_env({"MQTT_HOME_ID": "home-01", "MQTT_DEVICE_ID": "pi-led-01"})
