"""只读查询 Mixin：微博详情、列表、转发、评论、展开原文。"""

from __future__ import annotations

from .models import CommentItem, ListWeiboItem, RepostItem
from .normalizers import (
    assert_api_success,
    extract_status_payload,
    is_no_data_message,
    normalize_comment,
    normalize_mblog,
    normalize_positive_integer,
    normalize_repost,
    normalize_required_text,
)


class ReadMixin:
    """只读查询方法集。依赖 self.client 和 self.resolve_uid()。"""

    def list_own_weibos(self, limit: int, page: int, uid: str | None = None) -> list[ListWeiboItem]:
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        target_uid = normalize_required_text(uid, "uid") if uid else self.resolve_uid()  # type: ignore[attr-defined]
        response = self.client.request_json(  # type: ignore[attr-defined]
            "/api/container/getIndex",
            method="GET",
            query={"type": "uid", "value": target_uid, "containerid": f"107603{target_uid}", "page": normalized_page},
            headers={"referer": f"https://m.weibo.cn/u/{target_uid}"},
        )
        cards = ((response.get("data") or {}).get("cards") or [])
        if response.get("ok") == 0 and not cards:
            return []
        assert_api_success(response, "读取最近微博")
        items = [normalize_mblog(card.get("mblog")) for card in cards]
        return [item for item in items if item is not None][:normalized_limit]

    def show_weibo(self, weibo_id: str) -> ListWeiboItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(  # type: ignore[attr-defined]
            "/api/statuses/show",
            method="GET",
            query={"id": normalized_weibo_id},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        assert_api_success(response, "读取微博详情")
        item = normalize_mblog(extract_status_payload(response))
        if item is None:
            raise RuntimeError("微博详情接口返回成功，但缺少可解析的微博内容。")
        return item

    def get_reposts(self, weibo_id: str, limit: int, page: int) -> list[RepostItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(  # type: ignore[attr-defined]
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

    def get_comments(self, weibo_id: str, limit: int, page: int) -> list[CommentItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(  # type: ignore[attr-defined]
            "/api/comments/show",
            method="GET",
            query={"id": normalized_weibo_id, "page": normalized_page, "count": normalized_limit},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        if response.get("ok") == 0 and is_no_data_message(response.get("msg") or response.get("message")):
            return []
        assert_api_success(response, "读取微博评论")
        rows = (
            (response.get("data") or {}).get("data")
            or (response.get("data") or {}).get("list")
            or (response.get("data") or {}).get("comments")
            or []
        )
        items = [normalize_comment(row) for row in rows[:normalized_limit]]
        return [item for item in items if item is not None]

    def expand_reposted_status(self, items: list[ListWeiboItem]) -> None:
        """就地展开各条转发的原微博正文（失败时静默跳过）。"""
        for item in items:
            repost_info = item.reposted_status
            if not repost_info or not repost_info.id:
                continue
            try:
                original = self.show_weibo(repost_info.id)  # type: ignore[attr-defined]
                if original.text:
                    repost_info.text = original.text
                if original.user_name:
                    repost_info.user_name = original.user_name
            except Exception:  # noqa: BLE001
                continue
