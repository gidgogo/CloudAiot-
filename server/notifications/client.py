"""보호자 알림 서버로 이벤트를 보낸다."""

import logging

import requests

from shared.types import Intent

log = logging.getLogger(__name__)


class AlertClient:
    def __init__(self, server_url: str, timeout_sec: float = 1.0):
        self.server_url = server_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def send(self, intent: Intent, status: str = "requested") -> bool:
        payload = {
            "action": intent.action.value,
            "target": intent.target,
            "status": status,
            "timestamp": intent.timestamp,
        }
        try:
            r = requests.post(f"{self.server_url}/events", json=payload, timeout=self.timeout_sec)
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            log.warning("알림 전송 실패: %s", e)
            return False
