"""写操作 Mixin：发微博、评论、点赞、取消点赞、删除。"""

from __future__ import annotations

from .models import CommentItem, PostWeiboResult, WeiboActionResult
from .normalizers import (
    assert_api_success,
    extract_comment_payload,
    normalize_mblog,
    normalize_optional_string,
    normalize_required_text,
    stringify_id,
)
from .api_client import WeiboApiClient


class WriteMixin:
    """写操作方法集。依赖 self.client (WeiboApiClient)。"""

    def post_weibo(self, text: str) -> PostWeiboResult:
        content = normalize_required_text(text, "微博正文")
        response = self.client.request_json(  # type: ignore[attr-defined]
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

    def create_comment(self, weibo_id: str, text: str) -> CommentItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_text = normalize_required_text(text, "评论内容")
        response = self.client.request_json(  # type: ignore[attr-defined]
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
        item = normalize_comment_item(extract_comment_payload(response))
        if item is None:
            raise RuntimeError("评论接口返回成功，但缺少可解析的评论内容。")
        return item

    def like_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(  # type: ignore[attr-defined]
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
        response = self.client.request_json(  # type: ignore[attr-defined]
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
        try:
            response = self.client.request_json(  # type: ignore[attr-defined]
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
        except RuntimeError as err:
            # 如果服务端返回提示类似“链接 ... 无效”的错误，可能是对 Origin/Referer 校验比较严格。
            # 这种情况下尝试以 weibo.com origin/Referer 重试一次（兼容某些站点校验策略）。
            err_text = str(err) or ""
            trigger_tokens = ("链接", "无效", "Invalid URL", "invalid url")
            if any(tok in err_text for tok in trigger_tokens):
                try:
                    fallback_headers = {
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "x-requested-with": "XMLHttpRequest",
                        "origin": "https://weibo.com",
                        "referer": f"https://weibo.com/status/{normalized_weibo_id}",
                    }
                    # 有些场景下 weibo.com 的 ajax 路径更可靠，构造临时 client 指向 weibo.com 并调用 /ajax/statuses/destroy
                    alt_client = WeiboApiClient(session=self.client.session, store=getattr(self.client, "store", None), base_url="https://weibo.com")
                    response2 = alt_client.request_json(  # type: ignore[attr-defined]
                        "/ajax/statuses/destroy",
                        method="POST",
                        headers=fallback_headers,
                        data={"id": normalized_weibo_id},
                    )
                    assert_api_success(response2, "删除微博")
                    return WeiboActionResult(
                        action="删除成功",
                        weibo_id=normalized_weibo_id,
                        message=normalize_optional_string(response2.get("msg") or response2.get("message")) or "已删除这条微博（使用回退路径）。",
                        url=None,
                    )
                except Exception:
                    # 回退重试也失败，回退到原始错误以便上层显示完整信息
                    raise
            raise


# 延迟导入避免循环
def normalize_comment_item(raw):  # type: ignore[return]
    from .normalizers import normalize_comment
    return normalize_comment(raw)
