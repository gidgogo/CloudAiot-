from pathlib import Path

import pytest

from cloudaiot.config import DEFAULT_PATH, load_config
from cloudaiot.devices.controller import DeviceController, build_devices
from cloudaiot.intent.fusion import IntentFusion
from cloudaiot.types import GazeResult, GestureResult


def test_default_config_is_in_repository_root():
    assert DEFAULT_PATH.parent == Path(__file__).resolve().parents[1] / "config"
    cfg = load_config()
    assert cfg["camera"]["width"] > 0
    assert set(cfg["devices"]) == {"light", "fan"}


def test_explicit_config(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("camera:\n  width: 320\n", encoding="utf-8")
    assert load_config(custom)["camera"]["width"] == 320


def test_example_config_controls_mock_devices():
    cfg = load_config(DEFAULT_PATH.with_name("config.example.yaml"))
    devices = build_devices(cfg["devices"], mock=True)
    controller = DeviceController(devices)
    fusion = IntentFusion(
        cfg["gesture"]["mapping"],
        min_confidence=cfg["gesture"]["min_confidence"],
        **cfg["intent"],
    )
    for gesture, expected in [("open_palm", True), ("fist", False)]:
        intent = fusion.decide(GazeResult("light", 0.9), GestureResult(gesture, 0.9))
        assert intent is not None
        assert controller.execute(intent)
        assert devices["light"].is_on is expected
        assert not devices["fan"].is_on


def test_unimplemented_gpio_is_not_reported_as_working():
    with pytest.raises(NotImplementedError, match="GPIO"):
        build_devices({"light": {"type": "gpio_relay", "pin": 17}})
