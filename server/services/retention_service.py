"""제어 이력·도움 요청 보존 기간이 지난 데이터를 지운다(SAD 5.2, 6.2).

- 제어 이력: ACK 대기(PENDING)가 아닌 기록 중 발행 시각이 기준보다 오래된 것
- 도움 요청: 처리 완료(COMPLETED)된 요청 중 생성 시각이 기준보다 오래된 것
보존 기간이 None이면 지우지 않는다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from server.db.repositories import ControlEventRepository, HelpRequestRepository
from shared.types import now_ms

log = logging.getLogger(__name__)
DAY_MS = 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class PurgeResult:
    control_events: int = 0
    help_requests: int = 0


def purge_expired(
    session: Session,
    control_event_days: int | None,
    help_request_days: int | None,
    now: int | None = None,
) -> PurgeResult:
    now = now if now is not None else now_ms()
    control_events = help_requests = 0
    if control_event_days:
        control_events = ControlEventRepository(session).delete_finished_before(
            now - control_event_days * DAY_MS
        )
    if help_request_days:
        help_requests = HelpRequestRepository(session).delete_completed_before(
            now - help_request_days * DAY_MS
        )
    session.commit()
    if control_events or help_requests:
        log.info(
            "retention purge: control_events=%d help_requests=%d",
            control_events,
            help_requests,
        )
    return PurgeResult(control_events, help_requests)
