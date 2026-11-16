"""도움 요청 v1 JSON Schema 계약."""

import json
from pathlib import Path

import jsonschema

from shared.types import HelpRequest

SCHEMA = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "v1" / "help-request.schema.json"


def test_help_request_type_matches_v1_schema() -> None:
    request = HelpRequest(
        request_id="request-1", correlation_id="corr-1", user_id="user-01", created_at_ms=1,
    )
    jsonschema.validate(request.as_dict(), json.loads(SCHEMA.read_text(encoding="utf-8")))
