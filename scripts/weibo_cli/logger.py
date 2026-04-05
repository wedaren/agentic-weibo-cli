"""统一日志模块。

通过环境变量 WEIBO_LOG_LEVEL 控制级别（默认 WARNING）。
日志写入 .local/logs/weibo-cli.log，自动轮转（单文件最大 2 MB，保留 3 份）。
调试时可设置 WEIBO_LOG_LEVEL=DEBUG 或 WEIBO_LOG_LEVEL=INFO。

用法：
    from .logger import get_logger
    log = get_logger(__name__)
    log.info("请求 %s", url)
    log.debug("响应: %s", payload)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


_INITIALIZED: set[str] = set()

# 日志格式
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def _log_file_path() -> Path:
    """解析日志文件路径，兼容单测场景（无 weibo-cli 根目录时退回 /tmp）。"""
    try:
        root = Path(__file__).resolve().parents[2]
    except Exception:
        return Path("/tmp/weibo-cli.log")
    log_dir = root / ".local" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path("/tmp/weibo-cli.log")
    return log_dir / "weibo-cli.log"


def _resolve_level() -> int:
    """从环境变量读取日志级别，不合法时回退 WARNING。"""
    raw = os.environ.get("WEIBO_LOG_LEVEL", "WARNING").upper()
    return getattr(logging, raw, logging.WARNING)


def _setup_root_logger() -> None:
    """初始化根 logger（只执行一次）。"""
    root = logging.getLogger("weibo_cli")
    if root.handlers:
        return

    root.setLevel(_resolve_level())

    # 文件 handler：自动轮转
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            _log_file_path(),
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(file_handler)
    except OSError:
        pass  # 无法写文件时静默忽略，不影响主业务

    # 如果是 DEBUG/INFO，同时输出到 stderr 方便开发
    if root.level <= logging.INFO:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(stderr_handler)

    # 屏蔽底层库的噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取已配置的子 logger，调用方传入 __name__ 即可。"""
    _setup_root_logger()
    return logging.getLogger(name)
