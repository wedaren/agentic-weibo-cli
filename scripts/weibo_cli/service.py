"""微博业务服务层。

职责：封装对微博 API 的业务操作；不负责数据模型定义或 API 响应解析。
- 数据模型见 models.py
- API 响应解析见 normalizers.py
"""

from __future__ import annotations

from .api_client import WeiboApiClient
from .auth import WeiboAuthService

# 以下导入同时也充当向后兼容的公开 re-export（测试文件与 output.py 从此处导入）
from .models import (  # noqa: F401
    CommentItem,
    ListWeiboItem,
    PostWeiboResult,
    RepostItem,
    RepostedStatus,
    WeiboActionResult,
)
from .normalizers import (  # noqa: F401
    assert_api_success,
    extract_comment_payload,
    extract_status_payload,
    is_no_data_message,
    normalize_comment,
    normalize_mblog,
    normalize_optional_number,
    normalize_optional_string,
    normalize_positive_integer,
    normalize_repost,
    normalize_required_text,
    stringify_id,
)


class WeiboService:
    def __init__(self, client: WeiboApiClient):
        self.client = client
        self.resolved_uid: str | None = None

    @classmethod
    def create_default(cls) -> "WeiboService":
        auth = WeiboAuthService()
        session = auth.require_valid_session()
        return cls(WeiboApiClient(session=session, store=auth.store, base_url=auth.base_url))

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
        cards = ((response.get("data") or {}).get("cards") or [])
        if response.get("ok") == 0 and not cards:
            return []
        assert_api_success(response, "读取最近微博")
        items = [normalize_mblog(card.get("mblog")) for card in cards]
        return [item for item in items if item is not None][:normalized_limit]

    def show_weibo(self, weibo_id: str) -> ListWeiboItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
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

    def get_comments(self, weibo_id: str, limit: int, page: int) -> list[CommentItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(
            "/api/comments/show",
            method="GET",
            query={"id": normalized_weibo_id, "page": normalized_page, "count": normalized_limit},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        if response.get("ok") == 0 and is_no_data_message(response.get("msg") or response.get("message")):
            return []
        assert_api_success(response, "读取微博评论")
        rows = ((response.get("data") or {}).get("data") or (response.get("data") or {}).get("list") or (response.get("data") or {}).get("comments") or [])
        items = [normalize_comment(row) for row in rows[:normalized_limit]]
        return [item for item in items if item is not None]

    def create_comment(self, weibo_id: str, text: str) -> CommentItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_text = normalize_required_text(text, "评论内容")
        response = self.client.request_json(
            "/api/comments/create",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id, "content": normalized_text},
        )
        assert_api_success(response, "发表评论")
        item = normalize_comment(extract_comment_payload(response))
        if item is None:
            raise RuntimeError("评论接口返回成功，但缺少可解析的评论内容。")
        return item

    def like_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/attitudes/create",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id, "attitude": "heart"},
        )
        assert_api_success(response, "点赞微博")
        return WeiboActionResult(
            action="点赞成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已点赞这条微博。",
            url=f"https://m.weibo.cn/status/{normalized_weibo_id}",
        )

    def unlike_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/attitudes/destroy",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id},
        )
        assert_api_success(response, "取消点赞")
        return WeiboActionResult(
            action="取消点赞成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已取消点赞这条微博。",
            url=f"https://m.weibo.cn/status/{normalized_weibo_id}",
        )

    def delete_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/statuses/destroy",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id},
        )
        assert_api_success(response, "删除微博")
        return WeiboActionResult(
            action="删除成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已删除这条微博。",
            url=None,
        )

    def expand_reposted_status(self, items: list[ListWeiboItem]) -> None:
        """就地展开各条转发的原微博正文（失败时静默跳过）。

        通过 show_weibo 获取原微博完整正文和用户名，覆盖转发记录中截断的内容。
        """
        for item in items:
            repost_info = item.reposted_status
            if not repost_info or not repost_info.id:
                continue
            try:
                original = self.show_weibo(repost_info.id)
                if original.text:
                    repost_info.text = original.text
                if original.user_name:
                    repost_info.user_name = original.user_name
            except Exception:  # noqa: BLE001
                # 展开失败不应阻塞整体列表显示
                continue

    def resolve_uid(self) -> str:
        if self.resolved_uid:
            return self.resolved_uid
        session_uid = normalize_optional_string(self.client.session.uid)
        if session_uid:
            self.resolved_uid = session_uid
            return session_uid
        probe = self.client.validate_session()
        if not probe.uid:
            raise RuntimeError(
                "当前登录态缺少 uid。请先执行 status 确认状态；若登录态有效但缺少 uid，可补充 WEIBO_UID，"
                "否则执行 login 或 login --force 生成带 uid 的登录态。"
            )
        self.resolved_uid = probe.uid
        return probe.uid