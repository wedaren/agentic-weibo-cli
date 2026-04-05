"""普通微博使用能力测试。"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from weibo_cli.cli import build_parser
from weibo_cli.output import format_action_result, format_comment_result, format_comments, format_json_output, format_weibo_detail
from weibo_cli.service import CommentItem, ListWeiboItem, WeiboActionResult, WeiboService
from weibo_cli.session import SessionStatus


class FakeClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def request_json(self, path: str, **kwargs):
        self.calls.append({"path": path, **kwargs})
        return self.response


class ServiceExtensionTests(unittest.TestCase):
    def test_show_weibo_uses_status_show_endpoint(self) -> None:
        client = FakeClient(
            {
                "ok": 1,
                "data": {
                    "id": "123",
                    "bid": "Abc123",
                    "text": "<p>正文</p>",
                    "created_at": "刚刚",
                    "user": {"id": "42", "screen_name": "测试用户"},
                    "reposts_count": 1,
                    "comments_count": 2,
                    "attitudes_count": 3,
                },
            }
        )
        service = WeiboService(client)

        result = service.show_weibo("123")

        self.assertEqual(result.id, "123")
        self.assertEqual(result.user_name, "测试用户")
        self.assertEqual(client.calls[0]["path"], "/api/statuses/show")
        self.assertEqual(client.calls[0]["query"], {"id": "123"})

    def test_get_comments_uses_comments_show_endpoint(self) -> None:
        client = FakeClient(
            {
                "ok": 1,
                "data": {
                    "data": [
                        {
                            "id": "c1",
                            "text": "<span>评论内容</span>",
                            "created_at": "今天",
                            "user": {"id": "7", "screen_name": "评论者"},
                            "like_counts": 9,
                        }
                    ]
                },
            }
        )
        service = WeiboService(client)

        result = service.get_comments("123", limit=10, page=2)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "评论内容")
        self.assertEqual(client.calls[0]["path"], "/api/comments/show")
        self.assertEqual(client.calls[0]["query"], {"id": "123", "page": 2, "count": 10})

    def test_create_comment_uses_comments_create_endpoint(self) -> None:
        client = FakeClient(
            {
                "ok": 1,
                "data": {
                    "id": "c2",
                    "text": "已发送",
                    "created_at": "刚刚",
                    "user": {"id": "8", "screen_name": "我"},
                },
            }
        )
        service = WeiboService(client)

        result = service.create_comment("123", "已发送")

        self.assertEqual(result.id, "c2")
        self.assertEqual(client.calls[0]["path"], "/api/comments/create")
        self.assertEqual(client.calls[0]["data"], {"id": "123", "content": "已发送"})

    def test_like_and_delete_use_mutation_endpoints(self) -> None:
        service = WeiboService(FakeClient({"ok": 1, "msg": "操作成功"}))

        like_result = service.like_weibo("123")
        unlike_result = service.unlike_weibo("123")
        delete_result = service.delete_weibo("123")

        calls = service.client.calls
        self.assertEqual(calls[0]["path"], "/api/attitudes/create")
        self.assertEqual(calls[1]["path"], "/api/attitudes/destroy")
        self.assertEqual(calls[2]["path"], "/api/statuses/destroy")
        self.assertEqual(like_result.action, "点赞成功")
        self.assertEqual(unlike_result.action, "取消点赞成功")
        self.assertEqual(delete_result.action, "删除成功")


class CliExtensionTests(unittest.TestCase):
    def test_new_subcommands_are_registered(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.parse_args(["show", "--weibo-id", "123"]).handler.__name__, "handle_show")
        self.assertEqual(parser.parse_args(["comments", "--weibo-id", "123"]).handler.__name__, "handle_comments")
        self.assertEqual(parser.parse_args(["comment", "--weibo-id", "123", "--text", "hi"]).handler.__name__, "handle_comment")
        self.assertEqual(parser.parse_args(["like", "--weibo-id", "123"]).handler.__name__, "handle_like")
        self.assertEqual(parser.parse_args(["unlike", "--weibo-id", "123"]).handler.__name__, "handle_unlike")
        self.assertEqual(parser.parse_args(["delete", "--weibo-id", "123"]).handler.__name__, "handle_delete")

    def test_list_filter_flags_are_registered(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["list", "--limit", "5", "--only-reposts"])
        self.assertTrue(args.only_reposts)
        self.assertFalse(args.only_originals)

    def test_json_flag_is_available_before_and_after_subcommand(self) -> None:
        parser = build_parser()

        args_before = parser.parse_args(["--json", "status"])
        args_after = parser.parse_args(["list", "--json", "--limit", "5"])

        self.assertTrue(args_before.json)
        self.assertTrue(args_after.json)

    def test_list_rejects_conflicting_filters(self) -> None:
        from weibo_cli.cli import handle_list

        with self.assertRaises(RuntimeError):
            handle_list(SimpleNamespace(limit="5", page="1", only_reposts=True, only_originals=True))

    def test_list_can_filter_reposts_only(self) -> None:
        from weibo_cli.cli import handle_list

        items = [
            ListWeiboItem(
                id="1",
                bid=None,
                created_at=None,
                text="原创",
                user_name=None,
                user_id=None,
                reposted_status=None,
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            ),
            ListWeiboItem(
                id="2",
                bid=None,
                created_at=None,
                text="转发文案",
                user_name=None,
                user_id=None,
                reposted_status=SimpleNamespace(id="9", user_name="他人", text="原文"),
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            ),
        ]
        fake_service = SimpleNamespace(
            list_own_weibos=lambda limit, page: items,
            expand_reposted_status=lambda items: None,
        )
        output: list[str] = []

        with patch("weibo_cli.cli.WeiboService.create_default", return_value=fake_service), patch("sys.stdout.write", side_effect=output.append):
            handle_list(SimpleNamespace(limit="5", page="1", only_reposts=True, only_originals=False))

        rendered = "".join(output)
        self.assertIn("[1] 2", rendered)
        self.assertNotIn("[1] 1", rendered)

    def test_list_expands_reposted_original_if_available(self) -> None:
        from weibo_cli.cli import handle_list

        items = [
            ListWeiboItem(
                id="2",
                bid=None,
                created_at=None,
                text="转发文案",
                user_name=None,
                user_id=None,
                reposted_status=SimpleNamespace(id="9", user_name="他人", text="原文"),
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            ),
        ]

        def show_weibo(weibo_id: str):
            return ListWeiboItem(
                id=weibo_id,
                bid=None,
                created_at=None,
                text="原微博展开正文",
                user_name="原作者",
                user_id=None,
                reposted_status=None,
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            )

        def expand_reposted_status(repost_items: list) -> None:
            for item in repost_items:
                repost_info = item.reposted_status
                if repost_info and repost_info.id:
                    original = show_weibo(repost_info.id)
                    if original and original.text:
                        repost_info.text = original.text
                    if original and original.user_name:
                        repost_info.user_name = original.user_name

        fake_service = SimpleNamespace(
            list_own_weibos=lambda limit, page: items,
            show_weibo=show_weibo,
            expand_reposted_status=expand_reposted_status,
        )
        output: list[str] = []

        with patch("weibo_cli.cli.WeiboService.create_default", return_value=fake_service), patch("sys.stdout.write", side_effect=output.append):
            handle_list(SimpleNamespace(limit="5", page="1", only_reposts=True, only_originals=False))

        rendered = "".join(output)
        self.assertIn("原微博展开正文", rendered)

    def test_list_falls_back_to_recent_when_no_reposts(self) -> None:
        from weibo_cli.cli import handle_list

        items = [
            ListWeiboItem(
                id="1",
                bid=None,
                created_at=None,
                text="原创1",
                user_name=None,
                user_id=None,
                reposted_status=None,
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            ),
            ListWeiboItem(
                id="2",
                bid=None,
                created_at=None,
                text="原创2",
                user_name=None,
                user_id=None,
                reposted_status=None,
                source=None,
                reposts_count=None,
                comments_count=None,
                attitudes_count=None,
            ),
        ]

        fake_service = SimpleNamespace(
            list_own_weibos=lambda limit, page: items,
            expand_reposted_status=lambda items: None,
        )
        output: list[str] = []

        with patch("weibo_cli.cli.WeiboService.create_default", return_value=fake_service), patch("sys.stdout.write", side_effect=output.append):
            handle_list(SimpleNamespace(limit="5", page="1", only_reposts=True, only_originals=False))

        rendered = "".join(output)
        self.assertIn("未查询到转发，回退显示最近", rendered)
        self.assertIn("原创1", rendered)

    def test_list_uses_env_cookie_to_restore_when_create_default_fails(self) -> None:
        from weibo_cli.api_client import WeiboAuthError
        from weibo_cli.cli import handle_list

        fake_item = ListWeiboItem(
            id="10",
            bid=None,
            created_at=None,
            text="转发文案2",
            user_name=None,
            user_id=None,
            reposted_status=SimpleNamespace(id="11", user_name="他人2", text="原文2"),
            source=None,
            reposts_count=None,
            comments_count=None,
            attitudes_count=None,
        )

        fake_service = SimpleNamespace(
            list_own_weibos=lambda limit, page: [fake_item],
            show_weibo=lambda _id: None,
            expand_reposted_status=lambda items: None,
        )

        output: list[str] = []

        # First call to create_default raises, second returns the fake service
        with patch.dict("os.environ", {"WEIBO_COOKIE": "SUB=sub-val; XSRF-TOKEN=csrf", "WEIBO_UID": "123"}, clear=False), patch(
            "weibo_cli.cli.WeiboService.create_default", side_effect=[WeiboAuthError("expired", "https://m.weibo.cn"), fake_service]
        ), patch(
            "weibo_cli.cli.WeiboAuthService.inspect", return_value=SessionStatus(configured=True, usable=False, source="local", uid=None, updated_at=None, message="expired", session=None)
        ), patch("weibo_cli.cli.WeiboAuthService.persist_cookie_header", return_value=SimpleNamespace(session=None, persisted_path="/tmp", source_label="env", reused_existing_login=False, profile_dir=None, final_url=None, cookie_names=())), patch(
            "weibo_cli.cli.format_login_result", return_value="LOGIN_OK\n"
        ), patch("sys.stdout.write", side_effect=output.append):
            handle_list(SimpleNamespace(limit="5", page="1", only_reposts=True, only_originals=False))

        rendered = "".join(output)
        self.assertIn("LOGIN_OK", rendered)
        self.assertIn("10", rendered)

    def test_handle_status_can_emit_json(self) -> None:
        from weibo_cli.cli import handle_status

        output: list[str] = []
        status = SessionStatus(
            configured=True,
            usable=True,
            source="local",
            uid="123",
            updated_at="2026-04-05T00:00:00Z",
            message="ok",
            session=None,
        )

        with patch("weibo_cli.cli.WeiboAuthService.inspect", return_value=status), patch("sys.stdout.write", side_effect=output.append):
            handle_status(SimpleNamespace(json=True))

        payload = json.loads("".join(output))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["uid"], "123")
        self.assertEqual(payload["data"]["source"], "local")

    def test_main_returns_usage_exit_code_for_invalid_limit(self) -> None:
        from weibo_cli.cli import ExitCode, main

        with patch("sys.stderr.write"):
            exit_code = main(["list", "--limit", "0"])

        self.assertEqual(exit_code, int(ExitCode.USAGE))

    def test_main_returns_auth_exit_code_for_auth_error(self) -> None:
        from weibo_cli.api_client import WeiboAuthError
        from weibo_cli.cli import ExitCode, main

        with patch("weibo_cli.cli.WeiboAuthService.inspect", side_effect=WeiboAuthError("auth failed", "https://m.weibo.cn")), patch(
            "sys.stderr.write"
        ):
            exit_code = main(["status"])

        self.assertEqual(exit_code, int(ExitCode.AUTH))

    def test_main_emits_json_error_payload(self) -> None:
        from weibo_cli.api_client import WeiboAuthError
        from weibo_cli.cli import ExitCode, main

        stderr: list[str] = []
        with patch("weibo_cli.cli.WeiboAuthService.inspect", side_effect=WeiboAuthError("auth failed", "https://m.weibo.cn")), patch(
            "sys.stderr.write", side_effect=stderr.append
        ):
            exit_code = main(["status", "--json"])

        payload = json.loads("".join(stderr))
        self.assertEqual(exit_code, int(ExitCode.AUTH))
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["category"], "auth")


class OutputExtensionTests(unittest.TestCase):
    def test_format_weibo_detail_includes_author_and_counts(self) -> None:
        rendered = format_weibo_detail(
            ListWeiboItem(
                id="123",
                bid="Abc123",
                created_at="刚刚",
                text="正文",
                user_name="作者",
                user_id="42",
                reposted_status=None,
                source="iPhone",
                reposts_count=1,
                comments_count=2,
                attitudes_count=3,
            )
        )

        self.assertIn("作者: 作者 (42)", rendered)
        self.assertIn("互动: 转发 1 | 评论 2 | 点赞 3", rendered)

    def test_format_comments_and_actions(self) -> None:
        comments = format_comments(
            [
                CommentItem(
                    id="c1",
                    created_at="今天",
                    text="评论",
                    source="网页",
                    user_name="评论者",
                    user_id="7",
                    like_count=4,
                )
            ]
        )
        comment_result = format_comment_result(
            CommentItem(
                id="c2",
                created_at="刚刚",
                text="已发送",
                source="网页",
                user_name="我",
                user_id="8",
                like_count=0,
            )
        )
        action_result = format_action_result(
            WeiboActionResult(
                action="点赞成功",
                weibo_id="123",
                message="已点赞这条微博。",
                url="https://m.weibo.cn/status/123",
            )
        )

        self.assertIn("用户: 评论者 (7)", comments)
        self.assertIn("点赞: 4", comments)
        self.assertIn("评论成功", comment_result)
        self.assertIn("访问链接: https://m.weibo.cn/status/123", action_result)

    def test_format_json_output_wraps_success_payload(self) -> None:
        rendered = format_json_output({"items": [{"id": "1"}]})

        payload = json.loads(rendered)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["data"]["items"][0]["id"], "1")


class LongTextTests(unittest.TestCase):
    """验证 normalize_mblog 优先读取 longText.longTextContent 获取完整正文。"""

    def _make_mblog(self, **kwargs) -> dict:
        """构建最小化 mblog 字典，id 默认为 '1'。"""
        base = {"id": "1", "text": "截断正文 ​", "user": {}}
        base.update(kwargs)
        return base

    def test_long_text_content_takes_priority_over_text(self) -> None:
        """isLongText=True 时，应使用 longText.longTextContent 而非截断的 text。"""
        from weibo_cli.service import normalize_mblog

        raw = self._make_mblog(
            isLongText=True,
            longText={"longTextContent": "<p>完整的长文正文，超过 140 字。</p>"},
        )
        item = normalize_mblog(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item.text, "完整的长文正文，超过 140 字。")

    def test_falls_back_to_text_when_long_text_absent(self) -> None:
        """isLongText=True 但 longText 不存在时，回退到 text 字段（list 批量接口场景）。"""
        from weibo_cli.service import normalize_mblog

        raw = self._make_mblog(isLongText=True, text="截断正文 ​")
        item = normalize_mblog(raw)
        self.assertIsNotNone(item)
        self.assertIn("截断正文", item.text)

    def test_retweeted_status_uses_long_text_content(self) -> None:
        """转发的原微博如果是长文，也应优先读取 longText.longTextContent。"""
        from weibo_cli.service import normalize_mblog

        raw = self._make_mblog(
            retweeted_status={
                "id": "2",
                "isLongText": True,
                "longText": {"longTextContent": "<p>原微博完整内容</p>"},
                "text": "原微博截断 ​",
                "user": {"id": "99", "screen_name": "原作者"},
            }
        )
        item = normalize_mblog(raw)
        self.assertIsNotNone(item)
        self.assertIsNotNone(item.reposted_status)
        self.assertEqual(item.reposted_status.text, "原微博完整内容")

    def test_normal_short_text_unchanged(self) -> None:
        """isLongText=False 时，直接使用 text 字段，不做任何特殊处理。"""
        from weibo_cli.service import normalize_mblog

        raw = self._make_mblog(isLongText=False, text="<p>普通短文</p>")
        item = normalize_mblog(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item.text, "普通短文")


class DiskCacheTests(unittest.TestCase):
    """DiskCache 基本行为单元测试（依赖环境变量禁用不影响）。"""

    def setUp(self) -> None:
        import os
        import tempfile
        self._orig_disabled = os.environ.get("WEIBO_CACHE_DISABLED")
        # 测试中强制启用缓存，使用临时目录
        os.environ.pop("WEIBO_CACHE_DISABLED", None)
        self._tmpdir = tempfile.TemporaryDirectory()
        import weibo_cli.cache as cache_mod
        self._orig_cache_dir = cache_mod._cache_dir
        cache_mod._cache_dir = lambda: self._get_tmp_cache_dir()

    def _get_tmp_cache_dir(self):
        from pathlib import Path
        p = Path(self._tmpdir.name) / "cache"
        p.mkdir(exist_ok=True)
        return p

    def tearDown(self) -> None:
        import os
        import weibo_cli.cache as cache_mod
        cache_mod._cache_dir = self._orig_cache_dir
        self._tmpdir.cleanup()
        if self._orig_disabled is not None:
            os.environ["WEIBO_CACHE_DISABLED"] = self._orig_disabled
        else:
            os.environ.pop("WEIBO_CACHE_DISABLED", None)

    def test_set_and_get_returns_value(self) -> None:
        from weibo_cli.cache import DiskCache
        cache = DiskCache(ttl_sec=60)
        cache.set("test_key", {"value": 42})
        result = cache.get("test_key")
        self.assertEqual(result, {"value": 42})

    def test_get_returns_none_for_missing_key(self) -> None:
        from weibo_cli.cache import DiskCache
        cache = DiskCache(ttl_sec=60)
        self.assertIsNone(cache.get("nonexistent"))

    def test_expired_entry_returns_none(self) -> None:
        from weibo_cli.cache import DiskCache
        cache = DiskCache(ttl_sec=0)
        cache.set("expired_key", "data", ttl_sec=-1)
        self.assertIsNone(cache.get("expired_key"))

    def test_invalidate_removes_entry(self) -> None:
        from weibo_cli.cache import DiskCache
        cache = DiskCache(ttl_sec=60)
        cache.set("del_key", "val")
        cache.invalidate("del_key")
        self.assertIsNone(cache.get("del_key"))

    def test_clear_removes_all_entries(self) -> None:
        from weibo_cli.cache import DiskCache
        cache = DiskCache(ttl_sec=60)
        cache.set("k1", 1)
        cache.set("k2", 2)
        count = cache.clear()
        self.assertGreaterEqual(count, 2)
        self.assertIsNone(cache.get("k1"))


class FollowServiceTests(unittest.TestCase):
    """关注/粉丝/用户信息 service 层单元测试。"""

    def _make_service(self, response: dict) -> "WeiboService":
        import os
        os.environ["WEIBO_CACHE_DISABLED"] = "1"
        client = FakeClient(response)
        client.session = SimpleNamespace(uid="123456")  # type: ignore[attr-defined]
        return WeiboService(client)

    def tearDown(self) -> None:
        import os
        os.environ.pop("WEIBO_CACHE_DISABLED", None)

    def test_get_user_profile_returns_profile(self) -> None:
        response = {
            "ok": 1,
            "data": {
                "userInfo": {
                    "id": "999",
                    "screen_name": "测试用户",
                    "description": "简介内容",
                    "followers_count": 100,
                    "friends_count": 50,
                    "statuses_count": 200,
                    "verified": True,
                    "verified_reason": "官方认证",
                    "location": "北京",
                }
            },
        }
        svc = self._make_service(response)
        profile = svc.get_user_profile("999")
        self.assertEqual(profile.uid, "999")
        self.assertEqual(profile.screen_name, "测试用户")
        self.assertEqual(profile.followers_count, 100)
        self.assertTrue(profile.verified)

    def test_get_following_returns_follow_items(self) -> None:
        response = {
            "ok": 1,
            "data": {
                "cards": [
                    {"user": {"id": "111", "screen_name": "关注者A", "followers_count": 10, "friends_count": 5, "statuses_count": 20}},
                ]
            },
        }
        svc = self._make_service(response)
        items = svc.get_following("123456", page=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].uid, "111")
        self.assertEqual(items[0].screen_name, "关注者A")

    def test_get_followers_returns_empty_for_no_data(self) -> None:
        response = {"ok": 0, "msg": "没有更多数据了"}
        svc = self._make_service(response)
        items = svc.get_followers("123456", page=1)
        self.assertEqual(items, [])


class FollowOutputTests(unittest.TestCase):
    """输出层格式化测试。"""

    def test_format_user_profile(self) -> None:
        from weibo_cli.models import UserProfile
        from weibo_cli.output import format_user_profile
        profile = UserProfile(
            uid="123",
            screen_name="测试用户",
            description="简介",
            followers_count=100,
            friends_count=50,
            statuses_count=200,
            verified=True,
            verified_reason="官方认证",
            location="北京",
            profile_url="https://m.weibo.cn/u/123",
        )
        text = format_user_profile(profile)
        self.assertIn("测试用户", text)
        self.assertIn("粉丝 100", text)
        self.assertIn("官方认证", text)

    def test_format_follow_list_empty(self) -> None:
        from weibo_cli.output import format_follow_list
        text = format_follow_list([], label="关注")
        self.assertIn("暂无关注记录", text)

    def test_format_follow_list_items(self) -> None:
        from weibo_cli.models import FollowItem
        from weibo_cli.output import format_follow_list
        items = [FollowItem(
            uid="111", screen_name="用户A", description="简介A",
            followers_count=10, friends_count=5, statuses_count=20,
            verified=False, verified_reason=None,
        )]
        text = format_follow_list(items, label="粉丝")
        self.assertIn("用户A", text)
        self.assertIn("111", text)
        self.assertIn("粉丝 10", text)


if __name__ == "__main__":
    unittest.main()