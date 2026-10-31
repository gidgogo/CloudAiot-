from pathlib import Path

import pytest

from edge import config as edge_config
from edge.devices.controller import DeviceController, build_devices
from server import config as server_config
from server.intent.fusion import IntentFusion
from shared.config import load_yaml
from shared.types import GazeResult, GestureResult


@pytest.mark.parametrize("module, section", [(edge_config, "camera"), (server_config, "gaze")])
def test_component_example_config_works_outside_repository(monkeypatch, tmp_path, module, section):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "DEFAULT_PATH", tmp_path / "missing.yaml")
    assert module.load_config()[section]


def test_component_configs_are_separate():
    edge = edge_config.load_config(edge_config.EXAMPLE_PATH)
    server = server_config.load_config(server_config.EXAMPLE_PATH)
    assert set(edge) == {"camera", "edge", "devices"}
    assert set(server) == {"gaze", "gesture", "intent", "alert"}


def test_explicit_config(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("camera:\n  width: 320\n", encoding="utf-8")
    assert load_yaml(custom)["camera"]["width"] == 320
    assert edge_config.load_config(custom)["camera"]["width"] == 320


def test_example_configs_control_mock_devices():
    edge = edge_config.load_config(edge_config.EXAMPLE_PATH)
    server = server_config.load_config(server_config.EXAMPLE_PATH)
    devices = build_devices(edge["devices"], mock=True)
    controller = DeviceController(devices)
    fusion = IntentFusion(
        server["gesture"]["mapping"],
        min_confidence=server["gesture"]["min_confidence"],
        **server["intent"],
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


def test_runtime_components_do_not_import_each_other():
    import ast

    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "edge": {"server", "scripts"},
        "server": {"edge", "scripts"},
        "shared": {"edge", "server", "scripts"},
    }
    for component, blocked in forbidden.items():
        for path in (root / component).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                assert not {name.split(".")[0] for name in names} & blocked, path
