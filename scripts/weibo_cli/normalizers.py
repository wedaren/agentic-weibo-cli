"""微博 API 响应解析工具。

职责：原始 dict → 强类型模型，以及字符串/数值的标准化处理。
不包含业务逻辑，不发起网络请求。
"""

from __future__ import annotations

import html
import re
from typing import Any

from .models import CommentItem, FollowItem, ListWeiboItem, RepostItem, RepostedStatus, UserProfile


# ---------------------------------------------------------------------------
# 文本清理
# ---------------------------------------------------------------------------

def html_to_plain_text(value: str | None) -> str:
    """去除 HTML 标签，保留换行语义。"""
    normalized = normalize_optional_string(value)
    if not normalized:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def pick_full_text(raw: dict[str, Any] | None) -> str | None:
    """优先取 longText.longTextContent（长文完整正文），否则退回截断的 text 字段。

    微博 API 对超过约 300 字的长文会在 text 字段截断，同时设置 isLongText=True
    并在 longText.longTextContent 提供完整正文（show 接口才包含此字段）。
    """
    if not raw:
        return None
    if raw.get("isLongText"):
        full = normalize_optional_string((raw.get("longText") or {}).get("longTextContent"))
        if full:
            return full
    return raw.get("text")


# ---------------------------------------------------------------------------
# 值标准化
# ---------------------------------------------------------------------------

def normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"{field_name}不能为空。")
    return normalized


def normalize_positive_integer(value: int, field_name: str) -> int:
    if value <= 0:
        raise RuntimeError(f"{field_name} 必须是大于 0 的整数。")
    return value


def normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def stringify_id(value: Any) -> str | None:
    return normalize_optional_string(value)


def normalize_optional_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


# ---------------------------------------------------------------------------
# API 响应校验
# ---------------------------------------------------------------------------

def assert_api_success(response: dict[str, Any], action_name: str) -> None:
    if response.get("ok") in (1, None):
        return
    details = (
        normalize_optional_string(response.get("msg"))
        or normalize_optional_string(response.get("message"))
        or "接口未返回具体原因。"
    )
    raise RuntimeError(f"{action_name}失败：{details}")


def is_no_data_message(message: str | None) -> bool:
    normalized = normalize_optional_string(message)
    if normalized is None:
        return False
    no_data_phrases = ("还没有人转发过", "没有更多数据了", "暂无数据", "no data", "这里还没有内容", "还没有微博")
    return any(phrase in normalized for phrase in no_data_phrases)


# ---------------------------------------------------------------------------
# Payload 提取（处理接口响应结构差异）
# ---------------------------------------------------------------------------

def extract_status_payload(response: dict[str, Any]) -> dict[str, Any] | None:
    data = response.get("data")
    if isinstance(data, dict):
        status = data.get("status")
        if isinstance(status, dict):
            return status
        if stringify_id(data.get("id")):
            return data
    return response if stringify_id(response.get("id")) else None


def extract_comment_payload(response: dict[str, Any]) -> dict[str, Any] | None:
    data = response.get("data")
    if isinstance(data, dict):
        comment = data.get("comment")
        if isinstance(comment, dict):
            return comment
        if stringify_id(data.get("id")):
            return data
    return response if stringify_id(response.get("id")) else None


# ---------------------------------------------------------------------------
# 模型解析
# ---------------------------------------------------------------------------

def normalize_mblog(raw: dict[str, Any] | None) -> ListWeiboItem | None:
    """将 API 返回的 mblog 字典解析为 ListWeiboItem。"""
    weibo_id = stringify_id((raw or {}).get("id"))
    if not weibo_id:
        return None
    user = (raw or {}).get("user") or {}
    return ListWeiboItem(
        id=weibo_id,
        bid=normalize_optional_string((raw or {}).get("bid")),
        created_at=normalize_optional_string((raw or {}).get("created_at")),
        text=html_to_plain_text(pick_full_text(raw or {})),
        user_name=normalize_optional_string(user.get("screen_name")),
        user_id=stringify_id(user.get("id")),
        reposted_status=normalize_retweeted_status((raw or {}).get("retweeted_status")),
        source=normalize_optional_string((raw or {}).get("source")),
        reposts_count=normalize_optional_number((raw or {}).get("reposts_count")),
        comments_count=normalize_optional_number((raw or {}).get("comments_count")),
        attitudes_count=normalize_optional_number((raw or {}).get("attitudes_count")),
    )


def normalize_retweeted_status(raw: dict[str, Any] | None) -> RepostedStatus | None:
    """解析转发的原微博信息。"""
    if not raw:
        return None
    text = html_to_plain_text(pick_full_text(raw))
    user_name = normalize_optional_string((raw.get("user") or {}).get("screen_name"))
    repost_id = stringify_id(raw.get("id"))
    if not text and not user_name and not repost_id:
        return None
    return RepostedStatus(id=repost_id, user_name=user_name, text=text)


def normalize_repost(raw: dict[str, Any] | None) -> RepostItem | None:
    """解析他人对某条微博的转发记录。"""
    base = normalize_mblog(raw)
    if base is None:
        return None
    user = (raw or {}).get("user") or {}
    return RepostItem(
        id=base.id,
        created_at=base.created_at,
        text=base.text,
        source=base.source,
        user_name=normalize_optional_string(user.get("screen_name")),
        user_id=stringify_id(user.get("id")),
    )


def normalize_comment(raw: dict[str, Any] | None) -> CommentItem | None:
    """解析评论记录。"""
    comment_id = stringify_id((raw or {}).get("id"))
    if not comment_id:
        return None
    user = (raw or {}).get("user") or {}
    return CommentItem(
        id=comment_id,
        created_at=normalize_optional_string((raw or {}).get("created_at")),
        text=html_to_plain_text((raw or {}).get("text")),
        source=normalize_optional_string((raw or {}).get("source")),
        user_name=normalize_optional_string(user.get("screen_name")),
        user_id=stringify_id(user.get("id")),
        like_count=normalize_optional_number(
            (raw or {}).get("like_counts") or (raw or {}).get("like_count")
        ),
    )


def normalize_user_profile(raw: dict[str, Any] | None) -> UserProfile | None:
    """将 API 返回的用户信息字典解析为 UserProfile。"""
    uid = stringify_id((raw or {}).get("id"))
    if not uid:
        return None
    return UserProfile(
        uid=uid,
        screen_name=normalize_optional_string((raw or {}).get("screen_name")),
        description=normalize_optional_string((raw or {}).get("description")),
        followers_count=normalize_optional_number((raw or {}).get("followers_count")),
        friends_count=normalize_optional_number((raw or {}).get("friends_count")),
        statuses_count=normalize_optional_number((raw or {}).get("statuses_count")),
        verified=bool((raw or {}).get("verified")) if (raw or {}).get("verified") is not None else None,
        verified_reason=normalize_optional_string((raw or {}).get("verified_reason")),
        location=normalize_optional_string((raw or {}).get("location")),
        profile_url=normalize_optional_string((raw or {}).get("profile_url"))
            or (f"https://m.weibo.cn/u/{uid}" if uid else None),
    )


def normalize_follow_item(raw: dict[str, Any] | None) -> FollowItem | None:
    """将关注/粉丝列表条目解析为 FollowItem。"""
    uid = stringify_id((raw or {}).get("id"))
    if not uid:
        return None
    return FollowItem(
        uid=uid,
        screen_name=normalize_optional_string((raw or {}).get("screen_name")),
        description=normalize_optional_string((raw or {}).get("description")),
        followers_count=normalize_optional_number((raw or {}).get("followers_count")),
        friends_count=normalize_optional_number((raw or {}).get("friends_count")),
        statuses_count=normalize_optional_number((raw or {}).get("statuses_count")),
        verified=bool((raw or {}).get("verified")) if (raw or {}).get("verified") is not None else None,
        verified_reason=normalize_optional_string((raw or {}).get("verified_reason")),
    )
