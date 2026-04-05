"""本地微博 feed 数据库（SQLite）。

数据存储于 ~/.local/share/weibo-cli/feed.db。
仅保留最近 RETENTION_DAYS 天的数据（按首次同步时间 synced_at 计算）。
不依赖 models.py，以字典形式返回数据行，由上层负责格式化。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from .logger import get_logger

log = get_logger(__name__)

# 默认存储路径（用户级，跨仓库持久化）
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "weibo-cli" / "feed.db"

# 默认保留天数
RETENTION_DAYS = 7

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id               TEXT PRIMARY KEY,
    bid              TEXT,
    user_id          TEXT,
    user_name        TEXT,
    created_at       TEXT,
    synced_at        TEXT NOT NULL,
    text             TEXT NOT NULL DEFAULT '',
    repost_id        TEXT,
    repost_user_name TEXT,
    repost_text      TEXT,
    reposts_count    INTEGER,
    comments_count   INTEGER,
    attitudes_count  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_posts_user_id    ON posts(user_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_synced_at  ON posts(synced_at);
"""


class FeedDatabase:
    """本地 feed 数据库封装。每次使用建议新建实例，用完后调用 close()。"""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        log.debug("本地数据库已连接: %s", db_path)

    @property
    def path(self) -> Path:
        return self._path

    def insert_post(
        self,
        *,
        post_id: str,
        bid: str | None,
        user_id: str | None,
        user_name: str | None,
        created_at: str | None,
        synced_at: str,
        text: str,
        repost_id: str | None,
        repost_user_name: str | None,
        repost_text: str | None,
        reposts_count: int | None,
        comments_count: int | None,
        attitudes_count: int | None,
    ) -> bool:
        """插入一条微博。已存在（id 相同）则跳过，返回是否为本次新插入。"""
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO posts
               (id, bid, user_id, user_name, created_at, synced_at, text,
                repost_id, repost_user_name, repost_text,
                reposts_count, comments_count, attitudes_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                post_id, bid, user_id, user_name, created_at, synced_at, text,
                repost_id, repost_user_name, repost_text,
                reposts_count, comments_count, attitudes_count,
            ),
        )
        return cur.rowcount > 0

    def purge_old(self, retention_days: int = RETENTION_DAYS) -> int:
        """删除 synced_at 超过 retention_days 天的记录，返回删除条数。"""
        cutoff = time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.localtime(time.time() - retention_days * 86400),
        )
        cur = self._conn.execute("DELETE FROM posts WHERE synced_at < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def search(self, keyword: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """在 text / repost_text / user_name 中 LIKE 搜索，按发帖时间降序返回。"""
        pattern = f"%{keyword}%"
        rows = self._conn.execute(
            """SELECT * FROM posts
               WHERE text LIKE ?
                  OR repost_text LIKE ?
                  OR user_name LIKE ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_posts(
        self,
        *,
        user_id: str | None = None,
        user_name_filter: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """列出最近帖子，可按 user_id 或 user_name（精确匹配）过滤。"""
        if user_id:
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        elif user_name_filter:
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE user_name = ? ORDER BY created_at DESC LIMIT ?",
                (user_name_filter, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        """返回数据库统计信息。"""
        total = self._conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        oldest = self._conn.execute("SELECT MIN(synced_at) FROM posts").fetchone()[0]
        newest = self._conn.execute("SELECT MAX(synced_at) FROM posts").fetchone()[0]
        user_count = self._conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM posts WHERE user_id IS NOT NULL"
        ).fetchone()[0]
        return {
            "total": total,
            "user_count": user_count,
            "oldest_synced_at": oldest,
            "newest_synced_at": newest,
            "db_path": str(self._path),
            "retention_days": RETENTION_DAYS,
        }

    def total(self) -> int:
        """返回当前帖子总数。"""
        return self._conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()
