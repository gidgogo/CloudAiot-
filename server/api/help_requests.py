"""도움 요청 생성·조회·상태 변경 API.

- USER: 본인 요청 생성·조회
- GUARDIAN: 연결된 사용자의 요청 조회·확인·완료
- ADMIN: 전체 조회·변경, 사용자를 지정해 대신 생성
권한 규칙은 ``server/security/permissions.py``에 모여 있다.
"""

from fastapi import APIRouter

from server.api.deps import HelpServiceDep, Limit, Offset, PrincipalDep
from server.api.schemas import HelpRequestCreate, HelpRequestUpdate, ok
from server.db.models import HelpRequestRecord
from server.security.permissions import Principal, help_request_owner
from server.services.errors import web_error
from server.services.help_service import HelpService, help_request_to_dict
from shared.constants import API_PREFIX
from shared.types import HelpSource, HelpStatus

router = APIRouter(prefix=f"{API_PREFIX}/help-requests", tags=["help"])


def _visible(
    request_id: str, principal: Principal, service: HelpService
) -> HelpRequestRecord:
    record = service.get(request_id)
    if not principal.can_view_user(record.user_id):
        raise web_error("FORBIDDEN")
    return record


@router.get("")
def list_help_requests(
    principal: PrincipalDep,
    service: HelpServiceDep,
    status: HelpStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> dict:
    records, total = service.list(
        status=status, user_ids=principal.visible_user_ids, limit=limit, offset=offset
    )
    return ok(
        [help_request_to_dict(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=201)
def create_help_request(
    body: HelpRequestCreate, principal: PrincipalDep, service: HelpServiceDep
) -> dict:
    record = service.create(
        user_id=help_request_owner(principal, body.user_id),
        source=HelpSource.WEB,
        correlation_id=body.correlation_id,
    )
    return ok(help_request_to_dict(record))


@router.get("/{request_id}")
def get_help_request(
    request_id: str, principal: PrincipalDep, service: HelpServiceDep
) -> dict:
    return ok(help_request_to_dict(_visible(request_id, principal, service)))


@router.patch("/{request_id}")
def update_help_request(
    request_id: str,
    body: HelpRequestUpdate,
    principal: PrincipalDep,
    service: HelpServiceDep,
) -> dict:
    record = _visible(request_id, principal, service)
    if not principal.can_change_help_status(record.user_id):
        raise web_error("FORBIDDEN")
    return ok(
        help_request_to_dict(
            service.update_status(request_id, body.status, actor_id=principal.user_id)
        )
    )
