"""컴포넌트별 YAML 파일 로딩. 실행 위치와 무관하게 명시한 경로를 사용한다."""

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)
