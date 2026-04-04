"""微博业务动作。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from .api_client import WeiboApiClient


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


class WeiboService:
    def __init__(self, client: WeiboApiClient):
        self.client = client
        self.resolved_uid: str | None = None

    @classmethod
    def create_default(cls) -> "WeiboService":
        return cls(WeiboApiClient.from_configured_session())

    def post_weibo(self, text: str) -> PostWeiboResult:
        content = normalize_required_text(text, "微博正文")
        response = self.client.request_json(
            "/api/statuses/update",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": "https://m.weibo.cn/compose/",
            },
            data={"content": content},
        )
        assert_api_success(response, "发微博")
        status = (response.get("data") or {}).get("status")
        fallback_id = stringify_id((response.get("data") or {}).get("id"))
        item = normalize_mblog(status) if status else None
        weibo_id = item.id if item else fallback_id
        if not weibo_id:
            raise RuntimeError("发微博接口返回成功，但缺少微博 ID，无法确认发布结果。")
        bid = item.bid if item else normalize_optional_string((response.get("data") or {}).get("bid"))
        return PostWeiboResult(
            id=weibo_id,
            bid=bid,
            created_at=item.created_at if item else None,
            text=item.text if item else content,
            url=f"https://m.weibo.cn/status/{bid}" if bid else None,
        )

    def list_own_weibos(self, limit: int, page: int) -> list[ListWeiboItem]:
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        uid = self.resolve_uid()
        response = self.client.request_json(
            "/api/container/getIndex",
            method="GET",
            query={"type": "uid", "value": uid, "containerid": f"107603{uid}", "page": normalized_page},
            headers={"referer": f"https://m.weibo.cn/u/{uid}"},
        )
        if response.get("ok") == 0:
            return []
        cards = ((response.get("data") or {}).get("cards") or [])
        items = [normalize_mblog(card.get("mblog")) for card in cards]
        return [item for item in items if item is not None][:normalized_limit]

    def get_reposts(self, weibo_id: str, limit: int, page: int) -> list[RepostItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(
            "/api/statuses/repostTimeline",
            method="GET",
            query={"id": normalized_weibo_id, "page": normalized_page, "count": normalized_limit, "page_size": normalized_limit},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        if response.get("ok") == 0 and is_no_data_message(response.get("msg") or response.get("message")):
            return []
        assert_api_success(response, "查询微博转发")
        rows = ((response.get("data") or {}).get("data") or (response.get("data") or {}).get("list") or [])
        items = [normalize_repost(row) for row in rows[:normalized_limit]]
        return [item for item in items if item is not None]

    def resolve_uid(self) -> str:
        if self.resolved_uid:
            return self.resolved_uid
        session_uid = normalize_optional_string(self.client.session.uid)
        if session_uid:
            self.resolved_uid = session_uid
            return session_uid
        probe = self.client.validate_session()
        if not probe.uid:
            raise RuntimeError("当前登录态缺少 uid。请补充 WEIBO_UID，或重新运行 login 生成带 uid 的登录态。")
        self.resolved_uid = probe.uid
        return probe.uid


def normalize_mblog(raw: dict[str, Any] | None) -> ListWeiboItem | None:
    weibo_id = stringify_id((raw or {}).get("id"))
    if not weibo_id:
        return None
    retweeted_status = (raw or {}).get("retweeted_status") or None
    return ListWeiboItem(
        id=weibo_id,
        bid=normalize_optional_string((raw or {}).get("bid")),
        created_at=normalize_optional_string((raw or {}).get("created_at")),
        text=html_to_plain_text((raw or {}).get("text")),
        reposted_status=normalize_retweeted_status(retweeted_status),
        source=normalize_optional_string((raw or {}).get("source")),
        reposts_count=normalize_optional_number((raw or {}).get("reposts_count")),
        comments_count=normalize_optional_number((raw or {}).get("comments_count")),
        attitudes_count=normalize_optional_number((raw or {}).get("attitudes_count")),
    )


def normalize_retweeted_status(raw: dict[str, Any] | None) -> RepostedStatus | None:
    if not raw:
        return None
    text = html_to_plain_text(raw.get("text"))
    user_name = normalize_optional_string(((raw.get("user") or {}).get("screen_name")))
    repost_id = stringify_id(raw.get("id"))
    if not text and not user_name and not repost_id:
        return None
    return RepostedStatus(id=repost_id, user_name=user_name, text=text)


def normalize_repost(raw: dict[str, Any] | None) -> RepostItem | None:
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


def assert_api_success(response: dict[str, Any], action_name: str) -> None:
    if response.get("ok") in (1, None):
        return
    details = normalize_optional_string(response.get("msg")) or normalize_optional_string(response.get("message")) or "接口未返回具体原因。"
    raise RuntimeError(f"{action_name}失败：{details}")


def is_no_data_message(message: str | None) -> bool:
    normalized = normalize_optional_string(message)
    return normalized is not None and "还没有人转发过" in normalized


def html_to_plain_text(value: str | None) -> str:
    normalized = normalize_optional_string(value)
    if not normalized:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


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