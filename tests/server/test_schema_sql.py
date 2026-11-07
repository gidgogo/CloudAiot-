"""initial_schema.sql이 모델과 일치하는지 확인한다."""

from server.db.schema_sql import main


def test_initial_schema_is_up_to_date():
    assert main(["--check"]) == 0, (
        "모델이 바뀌었습니다. python -m server.db.schema_sql 을 실행하세요."
    )
