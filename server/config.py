"""서버 분석·알림 설정. 개인 설정이 없으면 동봉된 예제를 사용한다."""

from pathlib import Path

from shared.config import load_yaml

DEFAULT_PATH = Path(__file__).with_name("config.yaml")
EXAMPLE_PATH = Path(__file__).with_name("config.example.yaml")


def load_config(path: Path | None = None) -> dict:
    if path is None:
        path = DEFAULT_PATH if DEFAULT_PATH.exists() else EXAMPLE_PATH
    return load_yaml(path)
