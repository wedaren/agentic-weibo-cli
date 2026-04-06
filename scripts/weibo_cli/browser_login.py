"""浏览器扫码登录。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from .api_client import WeiboApiClient, WeiboAuthError
from .local_config import get_browser_profile_dir
from .session import CookieRecord, SessionData, merge_cookies, now_iso

DEFAULT_LOGIN_URL = "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fweibo.com"
AUTH_COOKIE_KEYS = ("SUB", "SUBP", "SCF")
BUSINESS_ORIGINS = ("https://weibo.com", "https://m.weibo.cn")


@dataclass(frozen=True, slots=True)
class BrowserLoginResult:
    cookies: tuple[CookieRecord, ...]
    uid: str | None
    login_url: str
    profile_dir: str
    final_url: str | None
    reused_existing_login: bool

    @property
    def cookie_names(self) -> tuple[str, ...]:
        return tuple(sorted({cookie.name for cookie in self.cookies}))


def find_browser_executable(browser_path: str | None = None) -> str:
    candidates = [
        (browser_path or "").strip() or None,
        os.environ.get("WEIBO_CHROME_PATH", "").strip() or None,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("未找到可用的 Chrome/Chromium 浏览器。请安装 Google Chrome，或通过 --browser-path / WEIBO_CHROME_PATH 指定浏览器路径。")


def assert_browser_automation_available(browser_path: str | None = None) -> str:
    from playwright.sync_api import sync_playwright

    executable_path = find_browser_executable(browser_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable_path, headless=True)
        browser.close()
    return executable_path


def run_browser_login(
    login_url: str | None = None,
    browser_path: str | None = None,
    timeout_ms: int = 180000,
    user_data_dir: str | None = None,
) -> BrowserLoginResult:
    from playwright.sync_api import sync_playwright

    executable_path = find_browser_executable(browser_path)
    resolved_login_url = (login_url or "").strip() or DEFAULT_LOGIN_URL
    profile_dir = resolve_browser_profile_dir(user_data_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 第一步：无头模式静默复用现有登录态，无需弹出浏览器窗口
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), executable_path=executable_path, headless=True
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            reused = try_reuse_existing_login(context, page, resolved_login_url, str(profile_dir))
            if reused is not None:
                return reused
        finally:
            context.close()

    # 第二步：无头模式未找到有效登录态，弹出可见浏览器让用户扫码
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), executable_path=executable_path, headless=False, viewport=None
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(resolved_login_url, wait_until="domcontentloaded")
            deadline = time.time() + timeout_ms / 1000
            while time.time() < deadline:
                hydrate_business_cookies(page)
                cookies = extract_weibo_cookies(context)
                if cookies:
                    probe = probe_uid(cookies)
                    if probe.get("uid") or probe.get("login") is not False:
                        return BrowserLoginResult(
                            cookies=cookies,
                            uid=str(probe.get("uid") or "").strip() or None,
                            login_url=resolved_login_url,
                            profile_dir=str(profile_dir),
                            final_url=str(page.url or resolved_login_url),
                            reused_existing_login=False,
                        )
                page.wait_for_timeout(2000)
        finally:
            context.close()
    raise RuntimeError(f"等待扫码登录超时（{round(timeout_ms / 1000)} 秒）。请确认你已在浏览器中完成微博登录。")


def resolve_browser_profile_dir(user_data_dir: str | None) -> Path:
    configured = (user_data_dir or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return get_browser_profile_dir()


def try_reuse_existing_login(context: object, page: object, login_url: str, profile_dir: str) -> BrowserLoginResult | None:
    for target_url in BUSINESS_ORIGINS:
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            continue
        cookies = extract_weibo_cookies(context)
        if not cookies:
            continue
        probe = probe_uid(cookies)
        if probe.get("uid") or probe.get("login") is not False:
            return BrowserLoginResult(
                cookies=cookies,
                uid=str(probe.get("uid") or "").strip() or None,
                login_url=login_url,
                profile_dir=profile_dir,
                final_url=str(page.url or target_url),
                reused_existing_login=True,
            )
    return None


def hydrate_business_cookies(page: object) -> None:
    for target_url in BUSINESS_ORIGINS:
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            continue


def extract_weibo_cookies(context: object) -> tuple[CookieRecord, ...]:
    raw_cookies = context.cookies(["https://m.weibo.cn", "https://weibo.com", "https://passport.weibo.com"])
    cookies: list[CookieRecord] = []
    for raw in raw_cookies:
        domain = str(raw.get("domain") or "")
        if "weibo" not in domain:
            continue
        cookies.append(
            CookieRecord(
                name=str(raw["name"]),
                value=str(raw["value"]),
                domain=domain.strip() or None,
                path=str(raw.get("path") or "/").strip() or "/",
                expires=int(raw["expires"]) if raw.get("expires") not in (None, -1) else None,
                secure=bool(raw.get("secure")),
                http_only=bool(raw.get("httpOnly")),
            )
        )
    deduped: tuple[CookieRecord, ...] = ()
    for cookie in cookies:
        deduped = merge_cookies(deduped, (cookie,))
    if not any(cookie.name in AUTH_COOKIE_KEYS for cookie in deduped):
        return ()
    return deduped


def probe_uid(cookies: tuple[CookieRecord, ...]) -> dict[str, object]:
    client = WeiboApiClient(
        session=SessionData(uid=None, login_url=None, updated_at=now_iso(), source="local", cookies=cookies)
    )
    try:
        result = client.validate_session()
        return {"uid": result.uid, "login": result.login}
    except WeiboAuthError:
        return {"uid": None, "login": False}


def try_headless_reuse(
    browser_path: str | None = None,
    user_data_dir: str | None = None,
    login_url: str | None = None,
) -> BrowserLoginResult | None:
    """仅使用无头浏览器尝试复用本地浏览器资料中的登录态。

    - 仅在 headless 模式下打开持久化 context 并运行复用检查。
    - 不会在复用失败时弹出可见浏览器窗口。
    - 若找到有效登录态，返回 BrowserLoginResult；否则返回 None。
    """
    from playwright.sync_api import sync_playwright

    executable_path = find_browser_executable(browser_path)
    resolved_login_url = (login_url or "").strip() or DEFAULT_LOGIN_URL
    profile_dir = resolve_browser_profile_dir(user_data_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), executable_path=executable_path, headless=True
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            return try_reuse_existing_login(context, page, resolved_login_url, str(profile_dir))
        finally:
            context.close()