"""微博 CLI 数据模型（纯数据类，无外部依赖）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RepostedStatus:
    id: str | None
    user_name: str | None
    text: str


@dataclass(slots=True)
class ListWeiboItem:
    id: str
    bid: str | None
    created_at: str | None
    text: str
    user_name: str | None
    user_id: str | None
    reposted_status: RepostedStatus | None
    source: str | None
    reposts_count: int | None
    comments_count: int | None
    attitudes_count: int | None


@dataclass(slots=True)
class PostWeiboResult:
    id: str
    bid: str | None
    created_at: str | None
    text: str
    url: str | None


@dataclass(slots=True)
class RepostItem:
    id: str
    created_at: str | None
    text: str
    source: str | None
    user_name: str | None
    user_id: str | None


@dataclass(slots=True)
class CommentItem:
    id: str
    created_at: str | None
    text: str
    source: str | None
    user_name: str | None
    user_id: str | None
    like_count: int | None


@dataclass(slots=True)
class WeiboActionResult:
    action: str
    weibo_id: str
    message: str | None
    url: str | None
