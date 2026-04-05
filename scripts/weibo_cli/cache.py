"""磁盘 TTL 缓存模块。

以 JSON 文件为载体，存放于 .local/cache/。
仅供只读操作使用（关注列表、粉丝列表、用户信息等），
写动作（发微博、评论、点赞）不应使用缓存。

用法：
    from .cache import DiskCache
    cache = DiskCache(ttl_sec=300)          # 5 分钟 TTL
    value = cache.get("following:123456")   # 未命中返回 None
    cache.set("following:123456", data)

可通过环境变量 WEIBO_CACHE_DISABLED=1 完全禁用缓存（单测方便）。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .logger import get_logger

log = get_logger(__name__)


def _cache_dir() -> Path:
    """解析缓存目录路径，必要时自动创建。"""
    try:
        root = Path(__file__).resolve().parents[2]
    except Exception:
        root = Path("/tmp")
    cache_dir = root / ".local" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _key_to_filename(key: str) -> str:
    """将任意缓存键转为安全文件名（sha256 前缀 + 可读后缀）。"""
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    # 保留 key 中的字母数字作为可读后缀，方便 ls .local/cache 时识别
    safe_suffix = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:40]
    return f"{digest}_{safe_suffix}.json"


class DiskCache:
    """简单磁盘 TTL 缓存。线程安全性依赖文件系统原子写（rename）。"""

    def __init__(self, ttl_sec: int = 300):
        self.ttl_sec = max(0, ttl_sec)
        self._disabled = os.environ.get("WEIBO_CACHE_DISABLED", "0") == "1"

    def _path(self, key: str) -> Path:
        return _cache_dir() / _key_to_filename(key)

    def get(self, key: str) -> Any | None:
        """读取缓存；未命中或已过期返回 None。"""
        if self._disabled:
            return None
        path = self._path(key)
        if not path.exists():
            log.debug("缓存未命中: %s", key)
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                envelope = json.load(f)
            expires_at = envelope.get("expires_at", 0)
            if time.time() > expires_at:
                log.debug("缓存已过期: %s", key)
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None
            log.debug("缓存命中: %s", key)
            return envelope.get("data")
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            log.warning("读取缓存文件失败 %s: %s", path, exc)
            return None

    def set(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        """写入缓存，通过临时文件 + rename 保证原子性。"""
        if self._disabled:
            return
        ttl = ttl_sec if ttl_sec is not None else self.ttl_sec
        envelope = {
            "key": key,
            "expires_at": time.time() + ttl,
            "data": value,
        }
        path = self._path(key)
        tmp_path = path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(envelope, f, ensure_ascii=False)
            tmp_path.replace(path)
            log.debug("缓存已写入: %s (ttl=%ds)", key, ttl)
        except OSError as exc:
            log.warning("写入缓存失败 %s: %s", path, exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def invalidate(self, key: str) -> None:
        """主动删除某个缓存条目。"""
        try:
            self._path(key).unlink(missing_ok=True)
            log.debug("缓存已失效: %s", key)
        except OSError as exc:
            log.warning("删除缓存条目失败 %s: %s", key, exc)

    def clear(self) -> int:
        """清空全部缓存文件，返回删除数量。"""
        count = 0
        try:
            for p in _cache_dir().glob("*.json"):
                try:
                    p.unlink()
                    count += 1
                except OSError:
                    pass
        except OSError as exc:
            log.warning("清除缓存目录失败: %s", exc)
        log.info("已清除 %d 个缓存条目", count)
        return count
