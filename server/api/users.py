"""사용자·보호자 연결 관리 API(ADMIN). 보호자·사용자는 자신이 볼 수 있는 범위만 조회한다.

열려 있는 실시간 연결에 대한 반영(연결 종료·열람 범위 갱신)은 UserService가 처리한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from server.api.deps import AdminUser, PrincipalDep, UserServiceDep
from server.api.schemas import GuardianLinkCreate, UserCreate, UserUpdate, ok
from server.services.errors import web_error
from server.services.user_service import link_to_dict, user_to_dict
from shared.constants import API_PREFIX
from shared.types import UserRole

router = APIRouter(prefix=API_PREFIX, tags=["users"])


@router.get("/users")
def list_users(
    principal: PrincipalDep, service: UserServiceDep, role: UserRole | None = None
) -> dict:
    visible = principal.visible_user_ids
    users = service.list(
        role=role, user_ids=None if visible is None else visible | {principal.user_id}
    )
    return ok([user_to_dict(user) for user in users])


@router.post("/users", status_code=201)
def create_user(body: UserCreate, _admin: AdminUser, service: UserServiceDep) -> dict:
    return ok(user_to_dict(service.create(**body.model_dump())))


@router.get("/users/{user_id}")
def get_user(user_id: str, principal: PrincipalDep, service: UserServiceDep) -> dict:
    if not principal.can_view_profile(user_id):
        raise web_error("FORBIDDEN")
    return ok(user_to_dict(service.get(user_id)))


@router.patch("/users/{user_id}")
def update_user(
    user_id: str, body: UserUpdate, admin: AdminUser, service: UserServiceDep
) -> dict:
    return ok(
        user_to_dict(
            service.update(
                user_id, body.model_dump(exclude_unset=True), actor_id=admin.user_id
            )
        )
    )


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, admin: AdminUser, service: UserServiceDep) -> Response:
    service.delete(user_id, actor_id=admin.user_id)
    return Response(status_code=204)


@router.get("/guardian-links")
def list_links(
    _admin: AdminUser,
    service: UserServiceDep,
    guardian_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    return ok(
        [
            link_to_dict(link)
            for link in service.list_links(guardian_id=guardian_id, user_id=user_id)
        ]
    )


@router.post("/guardian-links", status_code=201)
def create_link(
    body: GuardianLinkCreate, _admin: AdminUser, service: UserServiceDep
) -> dict:
    return ok(link_to_dict(service.link_guardian(body.guardian_id, body.user_id)))


@router.delete("/guardian-links/{guardian_id}/{user_id}", status_code=204)
def delete_link(
    guardian_id: str, user_id: str, _admin: AdminUser, service: UserServiceDep
) -> Response:
    service.unlink_guardian(guardian_id, user_id)
    return Response(status_code=204)
