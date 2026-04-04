"""本地配置读写。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def get_local_data_dir() -> Path:
    configured_dir = os.environ.get("WEIBO_CLI_DATA_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir).expanduser().resolve()
    return get_repo_root() / ".local"


def get_local_config_path() -> Path:
    return get_local_data_dir() / "weibo-session.json"


def read_local_config() -> dict[str, Any] | None:
    path = get_local_config_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_local_config(config: dict[str, Any]) -> Path:
    path = get_local_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(config, ensure_ascii=False, indent=2)}\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path