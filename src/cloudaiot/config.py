"""설정 파일(YAML) 로딩."""

from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
EXAMPLE_PATH = DEFAULT_PATH.with_name("config.example.yaml")


def load_config(path: Path = None) -> Dict[str, Any]:
    """config.yaml 을 읽고, 없으면 config.example.yaml 을 읽는다."""
    if path is None:
        path = DEFAULT_PATH if DEFAULT_PATH.exists() else EXAMPLE_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
