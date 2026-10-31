"""MQTT Topic 생성 규칙을 정의한다."""

def device_topic(home_id: str, device_id: str, suffix: str) -> str:
    return f"aiot/{home_id}/{device_id}/{suffix}"

