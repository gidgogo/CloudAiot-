"""기기 제어 이력 조회 API(로그인 사용자). 기록은 IoT 모듈이 ControlEventService로 남긴다."""

from fastapi import APIRouter

from server.api import ControlEventServiceDep, CurrentUser, Limit, Offset, ok
from server.services.control_event_service import control_event_to_dict
from shared.constants import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/control-events", tags=["control-events"])


@router.get("")
def list_control_events(_user: CurrentUser, service: ControlEventServiceDep, device_id: str | None = None,
                        limit: Limit = 50, offset: Offset = 0) -> dict:
    records, total = service.list(device_id=device_id, limit=limit, offset=offset)
    return ok([control_event_to_dict(record) for record in records], total=total, limit=limit, offset=offset)


@router.get("/{command_id}")
def get_control_event(command_id: str, _user: CurrentUser, service: ControlEventServiceDep) -> dict:
    return ok(control_event_to_dict(service.get(command_id)))
