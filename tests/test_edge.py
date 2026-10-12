import sys
from types import SimpleNamespace

import pytest

from edge.main import check_camera


@pytest.mark.parametrize("has_frame", [True, False])
def test_camera_check_closes_device(monkeypatch, capsys, has_frame):
    closed = []

    class FakeCamera:
        def __init__(self, **kwargs):
            assert kwargs["width"] == 640

        def open(self):
            pass

        def frames(self):
            if has_frame:
                yield SimpleNamespace(shape=(480, 640, 3))

        def close(self):
            closed.append(True)

    monkeypatch.setitem(sys.modules, "edge.camera", SimpleNamespace(Camera=FakeCamera))
    monkeypatch.setattr("edge.main.load_config", lambda _: {"camera": {"width": 640}})
    if has_frame:
        check_camera()
        assert "Camera OK: 640x480" in capsys.readouterr().out
    else:
        with pytest.raises(RuntimeError, match="No camera frame"):
            check_camera()
    assert closed == [True]
