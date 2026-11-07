"""모델에서 PostgreSQL DDL을 만들어 ``migrations/initial_schema.sql``을 갱신한다.

사용: ``python -m server.db.schema_sql``  (모델을 바꾼 뒤 실행)
확인만: ``python -m server.db.schema_sql --check``  (파일이 최신이 아니면 종료 코드 1)
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from server.db.models import Base

OUTPUT = Path(__file__).with_name("migrations") / "initial_schema.sql"
HEADER = """-- CloudAIoT 최초 스키마 (PostgreSQL)
-- server/db/models.py에서 생성했다. 직접 고치지 말고 `python -m server.db.schema_sql`로 다시 만든다.
-- 시간 컬럼(*_ms)은 UTC Unix 밀리초다.
"""


def render() -> str:
    dialect = postgresql.dialect()
    parts: list[str] = []
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
    body = "\n\n".join(parts)
    return HEADER + "\n" + "\n".join(line.rstrip() for line in body.splitlines()) + "\n"


def main(argv: list[str]) -> int:
    sql = render()
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != sql:
            print(f"{OUTPUT} is out of date. Run: python -m server.db.schema_sql")
            return 1
        return 0
    OUTPUT.write_text(sql, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
