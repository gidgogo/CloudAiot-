"""보호자 알림 서버.

디바이스가 보낸 이벤트(보호자 호출, 기기 제어 결과)를 시간·상태와 함께 기록한다.
실행: uvicorn server.app:app --reload
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CloudAiot 보호자 알림 서버")


class Event(BaseModel):
    action: str
    target: Optional[str] = None
    status: str
    timestamp: float


class EventRecord(Event):
    received_at: str


# TODO: SQLite 등 영구 저장소로 교체
EVENTS: List[EventRecord] = []


@app.post("/events")
def create_event(event: Event) -> EventRecord:
    record = EventRecord(**event.model_dump(), received_at=datetime.now(timezone.utc).isoformat())
    EVENTS.append(record)
    if event.action == "call_caregiver":
        # TODO: 보호자에게 푸시/문자 알림 전송
        pass
    return record


@app.get("/events")
def list_events(limit: int = 50) -> List[EventRecord]:
    return EVENTS[-limit:]
