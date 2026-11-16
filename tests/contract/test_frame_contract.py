"""영상 프레임 전송 규격 테스트 (공통 인터페이스 v1 5.4·5.5).

shared의 dataclass·상수와 shared/schemas의 기준 스키마가 서로 맞는지 확인한다.
송신자(Edge)와 수신자(AI 서버)가 같은 기준 파일을 쓰도록 하기 위한 테스트다.
"""
import json
from pathlib import Path

import jsonschema
import pytest

from shared.constants import FRAME_ACK_STATUSES, SCHEMA_VERSION
from shared.types import FrameAck, FrameMetadata

SCHEMAS = Path(__file__).resolve().parents[2] / "shared" / "schemas"


def schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_frame_metadata_dataclass_matches_schema():
    payload = FrameMetadata(edge_id="raspberrypi-01", camera_id="camera-01").as_dict()
    jsonschema.validate(payload, schema("frame-metadata.schema.json"))
    assert set(payload) == set(schema("frame-metadata.schema.json")["required"])


def test_frame_metadata_rejects_unknown_fields():
    payload = FrameMetadata(edge_id="raspberrypi-01", camera_id="camera-01").as_dict() | {"extra": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema("frame-metadata.schema.json"))


@pytest.mark.parametrize("status", sorted(FRAME_ACK_STATUSES))
def test_frame_ack_dataclass_matches_schema(status):
    payload = FrameAck(frame_id="e17d8451-59dd-4c45-92e0-3fdc018e72ab", status=status).as_dict()
    jsonschema.validate(payload, schema("frame-ack.schema.json"))
    assert set(payload) == set(schema("frame-ack.schema.json")["required"])


def test_ack_status_constant_matches_schema_enum():
    assert set(schema("frame-ack.schema.json")["properties"]["status"]["enum"]) == FRAME_ACK_STATUSES


def test_schema_version_constant_matches_schemas():
    for name in ("frame-metadata.schema.json", "frame-ack.schema.json"):
        assert schema(name)["properties"]["schema_version"]["const"] == SCHEMA_VERSION
