"""登录态与鉴权行为测试。"""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from weibo_cli.auth import LoginResult
from weibo_cli.api_client import WeiboApiClient, WeiboAuthError
from weibo_cli.browser_login import try_reuse_existing_login
from weibo_cli.cli import format_login_persistence_report, format_login_result, render_browser_login_instructions
from weibo_cli.session import CookieRecord, SessionData, SessionStore, merge_cookies, parse_cookie_header


class SessionPersistenceTests(unittest.TestCase):
    def test_session_store_accepts_cookie_jar_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            session_file = data_dir / "weibo-session.json"
            session_file.write_text(
                json.dumps(
                    {
                        "cookieJar": [
                            {"name": "SUB", "value": "sub-token", "domain": ".weibo.com", "path": "/", "expires": 123456},
                            {"name": "XSRF-TOKEN", "value": "csrf-token", "domain": "m.weibo.cn", "path": "/"},
                        ],
                        "uid": "123456",
                        "updatedAt": "2026-04-04T07:00:00Z",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"WEIBO_CLI_DATA_DIR": str(data_dir)}, clear=False):
                session = SessionStore().load()
            self.assertIsNotNone(session)
            assert session is not None
            self.assertEqual(session.uid, "123456")
            self.assertEqual(len(session.cookies), 2)
            self.assertIn("SUB=sub-token", session.cookie_header())
            self.assertIn("XSRF-TOKEN=csrf-token", session.cookie_header())

    def test_store_writes_version_two_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            session = SessionData(
                uid="123456",
                login_url="https://passport.weibo.com",
                updated_at="2026-04-04T07:00:00Z",
                source="local",
                cookies=(
                    CookieRecord(
                        name="SUB",
                        value="sub-token",
                        domain=".weibo.com",
                        path="/",
                        expires=123456,
                        secure=True,
                        http_only=True,
                    ),
                ),
            )
            with patch.dict("os.environ", {"WEIBO_CLI_DATA_DIR": str(data_dir)}, clear=False):
                SessionStore().save(session)
                raw = json.loads((data_dir / "weibo-session.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["version"], 2)
            self.assertEqual(raw["cookies"][0]["domain"], ".weibo.com")
            self.assertTrue(raw["cookies"][0]["http_only"])

    def test_merge_cookies_replaces_same_identity(self) -> None:
        existing = (CookieRecord(name="SUB", value="old", domain=".weibo.com", path="/"),)
        incoming = (CookieRecord(name="SUB", value="new", domain=".weibo.com", path="/"),)
        merged = merge_cookies(existing, incoming)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].value, "new")


class AuthBehaviorTests(unittest.TestCase):
    def test_application_auth_error_on_redirect_payload(self) -> None:
        session = SessionData(
            uid="123456",
            login_url=None,
            updated_at="2026-04-04T07:00:00Z",
            source="env",
            cookies=parse_cookie_header("SUB=sub-token; XSRF-TOKEN=csrf-token"),
        )
        client = WeiboApiClient(session=session)
        with self.assertRaises(WeiboAuthError):
            client.raise_for_application_auth_error(
                {"ok": -100, "url": "https://passport.weibo.com/sso/signin?entry=wapsso"},
                "https://m.weibo.cn/api/container/getIndex",
            )

    def test_application_auth_error_on_login_false_payload(self) -> None:
        session = SessionData(
            uid="123456",
            login_url=None,
            updated_at="2026-04-04T07:00:00Z",
            source="env",
            cookies=parse_cookie_header("SUB=sub-token; XSRF-TOKEN=csrf-token"),
        )
        client = WeiboApiClient(session=session)
        with self.assertRaises(WeiboAuthError):
            client.raise_for_application_auth_error(
                {"ok": 1, "data": {"login": False}},
                "https://m.weibo.cn/api/config",
            )

    def test_login_persistence_report_warns_when_cookie_jar_missing_domain(self) -> None:
        session = SessionData(
            uid="123456",
            login_url=None,
            updated_at="2026-04-04T07:00:00Z",
            source="local",
            cookies=(
                CookieRecord(
                    name="SUB",
                    value="sub-token",
                    domain=None,
                    path="/",
                    expires=None,
                    secure=False,
                    http_only=False,
                ),
            ),
        )

        report = format_login_persistence_report(session)
        self.assertIn("登录后校验: 已通过", report)
        self.assertIn("cookieJar 1 条", report)
        self.assertIn("缺少 domain 信息", report)


class BrowserLoginReuseTests(unittest.TestCase):
    def test_try_reuse_existing_login_returns_profile_login(self) -> None:
        fake_context = object()

        class FakePage:
            def __init__(self):
                self.url = ""

            def goto(self, target_url: str, wait_until: str, timeout: int):
                self.url = target_url

        page = FakePage()
        extracted = (
            CookieRecord(
                    name="SUB",
                    value="sub-token",
                    domain=".weibo.com",
                    path="/",
                    expires=None,
                    secure=False,
                    http_only=False,
                ),
            CookieRecord(name="XSRF-TOKEN", value="csrf-token", domain="m.weibo.cn", path="/"),
        )

        with patch("weibo_cli.browser_login.extract_weibo_cookies", return_value=extracted), patch(
            "weibo_cli.browser_login.probe_uid", return_value={"uid": "123456", "login": True}
        ):
            reused = try_reuse_existing_login(fake_context, page, "https://passport.weibo.com/login", "/tmp/browser-profile")

        self.assertIsNotNone(reused)
        assert reused is not None
        self.assertEqual(reused.uid, "123456")
        self.assertEqual(reused.cookie_names, ("SUB", "XSRF-TOKEN"))
        self.assertIn(reused.final_url, ("https://m.weibo.cn", "https://weibo.com"))

    def test_try_reuse_existing_login_marks_reused_state(self) -> None:
        fake_context = object()

        class FakePage:
            def __init__(self):
                self.url = ""

            def goto(self, target_url: str, wait_until: str, timeout: int):
                self.url = target_url

        page = FakePage()
        extracted = (CookieRecord(name="SUB", value="sub-token", domain=".weibo.com", path="/"),)

        with patch("weibo_cli.browser_login.extract_weibo_cookies", return_value=extracted), patch(
            "weibo_cli.browser_login.probe_uid", return_value={"uid": "123456", "login": True}
        ):
            reused = try_reuse_existing_login(fake_context, page, "https://passport.weibo.com/login", "/tmp/browser-profile")

        self.assertIsNotNone(reused)
        assert reused is not None
        self.assertTrue(reused.reused_existing_login)


class LoginOutputTests(unittest.TestCase):
    def test_render_browser_login_instructions_includes_profile_path(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            render_browser_login_instructions("https://passport.weibo.com/login", 3000, ".local/browser-profile")
        output = buffer.getvalue()
        self.assertIn("浏览器 profile", output)
        self.assertIn(".local/browser-profile", output)
        self.assertIn("先尝试复用", output)

    def test_format_login_result_for_reused_login_is_compact(self) -> None:
        session = SessionData(
            uid="123456",
            login_url="https://passport.weibo.com/login",
            updated_at="2026-04-04T07:00:00Z",
            source="local",
            cookies=(
                CookieRecord(name="SUB", value="sub-token", domain=".weibo.com", path="/"),
                CookieRecord(name="SUBP", value="subp-token", domain=".weibo.com", path="/"),
                CookieRecord(name="XSRF-TOKEN", value="csrf-token", domain="m.weibo.cn", path="/"),
            ),
        )
        output = format_login_result(
            LoginResult(
                session=session,
                persisted_path="/tmp/weibo-session.json",
                source_label="浏览器扫码",
                reused_existing_login=True,
                profile_dir="/tmp/browser-profile",
                final_url="https://m.weibo.cn/",
                cookie_names=("SUB", "SUBP", "XSRF-TOKEN"),
            )
        )
        self.assertIn("已复用当前 profile 中已有的微博登录态", output)
        self.assertIn("Cookie 摘要：3 个键", output)
        self.assertNotIn("捕获到的 cookie 键", output)


if __name__ == "__main__":
    unittest.main()