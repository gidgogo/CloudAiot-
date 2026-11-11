"""제스처·명령 매핑 조회(모든 로그인 사용자)·수정(ADMIN) API."""

from fastapi import APIRouter

from server.api.deps import AdminUser, CurrentUser, GestureMappingServiceDep
from server.api.schemas import GestureMappingUpdate, ok
from server.services.gesture_mapping_service import mapping_to_dict
from shared.constants import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/gesture-mappings", tags=["gesture-mappings"])


@router.get("")
def list_mappings(_user: CurrentUser, service: GestureMappingServiceDep) -> dict:
    return ok([mapping_to_dict(mapping) for mapping in service.list()])


@router.patch("/{gesture}")
def update_mapping(
    gesture: str,
    body: GestureMappingUpdate,
    _admin: AdminUser,
    service: GestureMappingServiceDep,
) -> dict:
    return ok(
        mapping_to_dict(service.update(gesture, body.model_dump(exclude_unset=True)))
    )
